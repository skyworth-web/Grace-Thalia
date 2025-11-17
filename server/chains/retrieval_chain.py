# server/chains/retrieval_chain.py

from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import os
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")

def ingest_docs():
    """Ingest resume and job description into Chroma vector store"""
    # Ensure directories exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)
    
    # Check if API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not set in ingest_docs()")
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    logger.info("🔄 Creating OpenAI embeddings...")
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    logger.info("✅ Embeddings model initialized")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Initialize or load existing Chroma database
    # If collection exists, delete it to start fresh
    try:
        if os.path.exists(CHROMA_DIR):
            import shutil
            shutil.rmtree(CHROMA_DIR)
            os.makedirs(CHROMA_DIR, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not clear existing database: {e}")
    
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=emb
    )
    
    all_docs = []
    
    # Process resume
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            docs = splitter.create_documents([text])
            # Add metadata to identify source
            for doc in docs:
                doc.metadata = {"source": "resume"}
            all_docs.extend(docs)
    
    # Process job description
    job_path = os.path.join(DATA_DIR, "job.txt")
    if os.path.exists(job_path):
        with open(job_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            docs = splitter.create_documents([text])
            for doc in docs:
                doc.metadata = {"source": "job_description"}
            all_docs.extend(docs)
    
    # Profile info removed - no longer needed
    
    if all_docs:
        logger.info(f"📚 Adding {len(all_docs)} document chunks to vector store...")
        chroma.add_documents(all_docs)
        chroma.persist()
        logger.info(f"✅ Successfully ingested {len(all_docs)} document chunks")
    else:
        logger.warning("⚠️ No documents to ingest")

def build_chain():
    """Build the conversational retrieval chain"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not set in build_chain()")
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    logger.info("🔄 Building conversational retrieval chain...")
    logger.info("   Model: gpt-4o-mini")
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        streaming=False
    )
    logger.info("✅ LLM initialized")
    
    logger.info("🔄 Loading embeddings model...")
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Load existing Chroma database
    if not os.path.exists(CHROMA_DIR):
        logger.error("❌ Vector store not found")
        raise ValueError("Vector store not found. Please ingest documents first.")
    
    logger.info("🔄 Loading Chroma vector store...")
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=emb
    )
    logger.info("✅ Vector store loaded")
    
    retriever = chroma.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )
    logger.info("✅ Retriever configured (k=4)")
    
    # Create chain with custom prompt
    from langchain.prompts import PromptTemplate
    
    template = """You are an AI interview assistant helping a candidate during a live interview.
Use the following pieces of context (resume, job description, and profile) to provide concise, helpful answer suggestions.

Context:
{context}

Current conversation:
{chat_history}

Question: {question}

Provide a brief, natural-sounding answer suggestion (2-3 sentences max) that:
1. Directly addresses the question
2. Incorporates relevant experience from the resume
3. Aligns with the job requirements
4. Sounds conversational and confident

Answer:"""
    
    QA_PROMPT = PromptTemplate(
        template=template,
        input_variables=["context", "chat_history", "question"]
    )
    
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=False,
        verbose=False,
        combine_docs_chain_kwargs={"prompt": QA_PROMPT}
    )
    
    logger.info("✅ Conversational retrieval chain built successfully")
    return chain


def build_retriever(k: int = 5):
    """Load Chroma vector store and return a retriever instance."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    emb = OpenAIEmbeddings(model="text-embedding-3-small")

    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store not found. Please ingest documents first.")

    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=emb
    )

    return chroma.as_retriever(search_type="similarity", search_kwargs={"k": k})
