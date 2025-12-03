# server/routers/health.py

from fastapi import APIRouter
import os
import logging

from config import OPENAI_API_KEY, generator_chain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    """Health check endpoint."""
    # Check if vector store exists and has documents
    chroma_exists = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "data", "chroma"))
    doc_count = 0
    if chroma_exists:
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_chroma import Chroma
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            chroma = Chroma(
                persist_directory=os.path.join(os.path.dirname(__file__), "..", "data", "chroma"),
                embedding_function=embeddings,
            )
            # Try to get document count
            try:
                all_docs = chroma.get()
                doc_count = len(all_docs.get('ids', [])) if all_docs else 0
            except:
                pass
        except Exception as e:
            logger.debug(f"Could not check document count: {e}")
    
    return {
        "status": "ok",
        "api_key": bool(OPENAI_API_KEY),
        "chain_initialized": generator_chain is not None,
        "chroma_exists": chroma_exists,
        "document_count": doc_count
    }

