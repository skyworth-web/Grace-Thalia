# server/routers/ingest.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging

from chains.retrieval_chain import ingest_docs
from chains.generator_chain import build_generator_chain
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestPayload(BaseModel):
    resume: str
    job: Optional[str] = ""


@router.post("")
async def ingest(payload: IngestPayload):
    """Ingest resume and job description into vector store."""
    global chain, generator_chain
    chain = config.chain
    generator_chain = config.generator_chain

    try:
        # Save resume and job to files
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)

        resume_path = os.path.join(data_dir, "resume.txt")
        job_path = os.path.join(data_dir, "job.txt")

        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(payload.resume)

        with open(job_path, "w", encoding="utf-8") as f:
            f.write(payload.job)

        # Ingest into vector store
        ingest_docs()

        # Rebuild chains
        from chains.retrieval_chain import build_chain
        config.chain = build_chain()
        config.generator_chain = build_generator_chain()
        chain = config.chain
        generator_chain = config.generator_chain

        logger.info("✅ Resume and job description ingested successfully")
        return {"status": "ok", "message": "Resume and job description ingested successfully"}

    except Exception as e:
        logger.error(f"Ingest error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

