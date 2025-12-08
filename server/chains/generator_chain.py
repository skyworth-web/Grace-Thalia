# server/chains/generator_chain.py

import os
import logging
from operator import itemgetter

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableMap, RunnableLambda

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")


def _load_full_resume() -> str:
    """Load the full resume text from file (1-2 pages, perfect for full context)."""
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    if os.path.exists(resume_path):
        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                logger.info(f"📄 Loaded full resume ({len(text)} chars)")
                return text
        except Exception as e:
            logger.warning(f"⚠ Could not load full resume: {e}")
    return ""


# ============================================================
# Build Unified Generator Chain (Transcript + Resume RAG)
# ============================================================
def build_generator_chain():
    """
    Retrieval-augmented generation pipeline that uses:
    - transcript context (live STT)
    - resume/job context
    - summary context (optional)
    """

    if not os.path.exists(CHROMA_DIR):
        logger.warning("⚠ Vector DB missing — using simple chain.")
        return _build_simple_chain()

    # LLM for generation (streaming enabled)
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.3,
        streaming=True,
        max_tokens=500,
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    # --- Retrievers ---
    transcript_retriever = chroma.as_retriever(
        search_kwargs={"k": 6},
        filter={"type": "transcript"}
    )

    resume_retriever = chroma.as_retriever(
        search_kwargs={"k": 6},
        filter={"type": "resume"}
    )

    summary_retriever = chroma.as_retriever(
        search_kwargs={"k": 3},
        filter={"type": "summary"}
    )

    # ============================================================
    # HELPERS
    # ============================================================

    def retrieve_transcript(inputs):
        q = inputs.get("transcript", "")
        docs = transcript_retriever.invoke(q)
        logger.info(f"🗣 Retrieved {len(docs)} transcript chunks")
        return docs

    def retrieve_resume(inputs):
        # Still retrieve relevant chunks for additional context, but we'll use full resume as primary
        q = inputs.get("transcript", "")
        docs = resume_retriever.invoke(q)
        logger.info(f"📄 Retrieved {len(docs)} resume chunks (supplementary)")
        return docs
    
    def get_full_resume(inputs):
        # Load full resume text - this is the PRIMARY source for resume info
        full_resume = _load_full_resume()
        return full_resume

    def retrieve_summary(inputs):
        try:
            q = inputs.get("transcript", "")
            docs = summary_retriever.invoke(q)
            logger.info(f"🧾 Retrieved {len(docs)} summary chunks")
            return docs
        except Exception:
            return []

    def format_docs(docs):
        parts = []
        for d in docs:
            meta = d.metadata.get("type", "unknown")
            parts.append(f"[{meta}] {d.page_content}")
        return "\n\n".join(parts)

    # ============================================================
    # PROMPT TEMPLATE (clean + transcript-first)
    # ============================================================
    prompt = PromptTemplate(
        input_variables=[
            "transcript_context",
            "full_resume_text",
            "resume_context",
            "summary_context",
            "transcript",
            "chat_history",
            "full_interview_context"
        ],
        template="""
You are an advanced INTERVIEW COPILOT.  
Your job is to produce a natural, spoken answer for the candidate.

====================================================
📄 **COMPLETE RESUME (FULL TEXT - PRIMARY SOURCE)**  
THIS IS THE CANDIDATE'S COMPLETE RESUME. Study it carefully and use it as the PRIMARY source for all resume-related questions.
Use specific details from this resume - names, companies, technologies, projects, achievements.
NEVER use placeholder text like "[your field]" or "[mention key responsibilities]".
ALWAYS use actual information from this resume:

{full_resume_text}

====================================================
🎙 **CONVERSATION HISTORY (Transcript-Based Context)**  
Use this FIRST and MOST IMPORTANT when answering:
{transcript_context}

====================================================
📄 **SUPPLEMENTARY RESUME CHUNKS (If needed for additional context)**  
These are semantic search results - use only if full resume above doesn't cover something:
{resume_context}

====================================================
🧠 **PAST SUMMARY CONTEXT (If available)**  
Use this to avoid repeating mistakes and improve consistency:
{summary_context}

====================================================
💬 **WHAT THE INTERVIEWER JUST SAID:**  
"{transcript}"

====================================================
📝 **FULL INTERVIEW CONTEXT:**  
(Use lightly — avoid repetition)
{full_interview_context}

====================================================
### 🔥 TASK
Generate an answer the candidate should SAY OUT LOUD.

RULES:
- Keep it 2–4 sentences.
- Be confident, conversational, and natural.
- Use FIRST PERSON ("I", "my experience…")
- DO NOT repeat the interviewer's question.
- Ground answer in transcript FIRST.
- ALWAYS use ACTUAL details from the complete resume above.
- NEVER use placeholder text or generic statements.
- Use specific: company names, technologies, project names, achievements from the resume.
- Sound human, not scripted.

Now produce ONLY the candidate's spoken answer:
""",
    )

    # ============================================================
    # BUILD LCEL PIPELINE
    # ============================================================

    chain = (
        RunnableMap({
            "transcript_context": RunnableLambda(retrieve_transcript) | RunnableLambda(format_docs),
            "full_resume_text": RunnableLambda(get_full_resume),  # Full resume as primary source
            "resume_context": RunnableLambda(retrieve_resume) | RunnableLambda(format_docs),  # Supplementary chunks
            "summary_context": RunnableLambda(retrieve_summary) | RunnableLambda(format_docs),
            "transcript": itemgetter("transcript"),
            "chat_history": itemgetter("chat_history"),
            "full_interview_context": itemgetter("full_interview_context"),
        })
        | prompt
        | llm
        | StrOutputParser()
    )

    chain = chain | RunnableLambda(lambda text: {"answer": text})
    logger.info("✅ Generator chain ready (Transcript + Resume RAG Active)")
    return chain


# ============================================================
# SIMPLE FALLBACK CHAIN
# ============================================================
def _build_simple_chain():
    logger.warning("⚠ Using fallback generator (no RAG, but will use full resume if available).")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3, streaming=True)

    def get_resume_for_fallback(inputs):
        full_resume = _load_full_resume()
        return full_resume if full_resume else "No resume available."

    prompt = PromptTemplate(
        input_variables=["transcript", "full_resume_text"],
        template="""
You are an interview copilot. Generate a natural, confident 2–4 sentence spoken answer.

====================================================
📄 **CANDIDATE'S COMPLETE RESUME:**
{full_resume_text}

====================================================
💬 **INTERVIEWER'S QUESTION:**
"{transcript}"

====================================================
### TASK
Generate an answer the candidate should SAY OUT LOUD using:
- ACTUAL details from the resume above (names, companies, technologies, projects)
- NEVER use placeholder text like "[your field]" or generic statements
- Use FIRST PERSON ("I", "my experience…")
- Be specific and confident

Answer:
""",
    )

    chain = (
        RunnableMap({
            "transcript": itemgetter("transcript"),
            "full_resume_text": RunnableLambda(get_resume_for_fallback),
        })
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain | RunnableLambda(lambda x: {"answer": x})
