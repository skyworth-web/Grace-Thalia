# server/chains/retrieval_chain.py

import os
import logging
from operator import itemgetter

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")


# ---------------------------
# INGEST DOCUMENTS
# ---------------------------
def ingest_docs() -> None:
    """
    Read resume.txt and job.txt from ../data, split into chunks,
    and store them in a persistent Chroma vector store.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    # Clean out old vector store
    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    # Smaller chunks with more overlap for better context preservation
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,  # Smaller chunks for better precision
        chunk_overlap=300,  # More overlap to preserve context
        separators=["\n\n", "\n", ". ", " ", ""]  # Better splitting for resumes
    )

    # Create Chroma store
    chroma = Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )

    docs = []

    # Resume ingestion with better metadata
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    resume_summary = None
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            # Extract key resume info for quick access
            resume_summary = _extract_resume_summary(text)
            
            # Split resume into chunks with better metadata
            for d in splitter.create_documents([text]):
                d.metadata = {
                    "source": "resume",
                    "type": "resume",
                    "summary": resume_summary  # Include summary in metadata for easy access
                }
                docs.append(d)
            
            # Also add a summary document for quick retrieval
            if resume_summary:
                from langchain_core.documents import Document
                summary_doc = Document(
                    page_content=f"RESUME SUMMARY:\n{resume_summary}",
                    metadata={"source": "resume_summary", "type": "summary"}
                )
                docs.append(summary_doc)

    # Job description ingestion
    job_path = os.path.join(DATA_DIR, "job.txt")
    if os.path.exists(job_path):
        with open(job_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            for d in splitter.create_documents([text]):
                d.metadata = {"source": "job"}
                docs.append(d)

    if not docs:
        logger.warning("⚠ No documents to ingest")
        return

    # Add docs (auto-persist on write)
    chroma.add_documents(docs)

    logger.info("✅ Ingestion complete (%d chunks)", len(docs))
    if resume_summary:
        logger.info(f"📋 Resume summary: {resume_summary[:100]}...")


def _extract_resume_summary(resume_text: str) -> str:
    """Extract key information from resume using LLM."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import PromptTemplate
        
        # Check if OpenAI client is available
        import os
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("⚠️ OPENAI_API_KEY not set, skipping resume summary extraction")
            return ""
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, timeout=10)
        
        prompt = PromptTemplate(
            input_variables=["resume"],
            template="""Extract key information from this resume. Provide a concise summary in this exact format:

NAME: [Full name if available, otherwise "Not specified"]
TITLE/ROLE: [Current or most recent job title]
YEARS_OF_EXPERIENCE: [Total years of professional experience, estimate if not explicit]
KEY_SKILLS: [Top 5-7 most important skills/technologies, comma-separated]
EDUCATION: [Highest degree and field]
KEY_ACHIEVEMENTS: [2-3 most impressive achievements or projects, one per line]

Resume text:
{resume}

Provide ONLY the summary in the format above, nothing else. If information is not available, write "Not specified"."""
        )
        
        chain = prompt | llm
        # Limit to first 4000 chars to avoid token limits
        limited_resume = resume_text[:4000] if len(resume_text) > 4000 else resume_text
        summary = chain.invoke({"resume": limited_resume})
        result = summary.content if hasattr(summary, 'content') else str(summary)
        logger.info(f"✅ Extracted resume summary: {result[:100]}...")
        return result
    except Exception as e:
        logger.warning(f"⚠️ Could not extract resume summary: {e}")
        # Fallback: try to extract basic info from first lines
        lines = [line.strip() for line in resume_text.split('\n')[:15] if line.strip()]
        fallback = "\n".join(lines)
        logger.info(f"📋 Using fallback summary (first 15 lines)")
        return fallback


# ---------------------------
# BUILD RETRIEVAL CHAIN — LCEL
# ---------------------------
def build_chain():
    """
    Build an LCEL retrieval chain that matches the old
    ConversationalRetrievalChain interface:

    chain.invoke({"question": str, "chat_history": list}) -> {"answer": str}
    """
    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store missing — run /ingest first")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.6,
        streaming=False,
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    retriever = chroma.as_retriever(search_kwargs={"k": 4})

    prompt = PromptTemplate(
        input_variables=["context", "question", "chat_history"],
        template="""
You are an expert interview answer assistant helping a candidate respond to interview questions.

CANDIDATE'S BACKGROUND (from resume and job description):
{context}

Previous conversation:
{chat_history}

Interview question: {question}

Generate a smart, personalized answer (2-4 sentences) that:
• Uses SPECIFIC details from the candidate's resume and experience
• Highlights relevant skills, projects, or achievements that match the question
• Aligns with the job requirements (if job description was provided)
• Sounds natural and conversational
• Shows confidence and professionalism
• Uses concrete examples when relevant

IMPORTANT:
- ALWAYS reference specific details from the candidate's background
- Connect their experience to the question being asked
- Keep it concise (2-4 sentences)
- Make it sound like a real person speaking
- NEVER make up experiences not in the resume

Answer:
"""
    )

    # LCEL graph
    base_chain = (
        RunnableMap(
            {
                "context": itemgetter("question") | retriever,
                "question": itemgetter("question"),
                "chat_history": itemgetter("chat_history"),
            }
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    # Match old ConversationalRetrievalChain interface
    chain = base_chain | RunnableLambda(lambda text: {"answer": text})

    logger.info("✅ LCEL Retrieval chain ready")
    return chain


# ---------------------------
# SIMPLE RETRIEVER (optional)
# ---------------------------
def build_retriever(k: int = 5):
    """
    Just return a retriever instance if you want to use it elsewhere.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store missing — run /ingest first")

    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    return chroma.as_retriever(search_kwargs={"k": k})
