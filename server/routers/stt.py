# server/routers/stt.py

from fastapi import APIRouter, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
import asyncio
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import config
from services.stt_service import transcribe_audio
from services.transcript_reconciliation import add_transcript, clear_buffer
from chains.retrieval_chain import append_transcript_chunk_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt", tags=["stt"])

# STT executor for async transcription
stt_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="STT")
# Vector DB executor for non-blocking operations
vector_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="VectorDB")


@router.post("")
async def stt(file: UploadFile = File(...)):
    """STT endpoint with backend reconciliation."""
    if config.client is None:
        return JSONResponse(
            status_code=400,
            content={"transcript": "", "error": "OpenAI client not initialized. Set OPENAI_API_KEY."}
        )

    try:
        audio_bytes = await file.read()
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            stt_executor,
            transcribe_audio,
            config.client,
            audio_bytes,
            file.filename,
            file.content_type
        )

        if result and result.strip():
            raw_text = result.strip()
            
            # Add to reconciliation buffer and get reconciled text
            display_text, full_transcript = add_transcript(raw_text)
            
            logger.info(f"📝 STT transcript: {raw_text[:50]}...")
            
            # Store in vector DB asynchronously (non-blocking) for better performance
            # This doesn't block the STT response, improving latency
            if full_transcript:
                loop.run_in_executor(
                    vector_db_executor,
                    append_transcript_chunk_async,
                    full_transcript,
                    "unknown",
                    str(datetime.now())
                )
            
            return {
                "transcript": display_text,
                "full_transcript": full_transcript
            }
        else:
            # No new transcript, but return current reconciled text
            display_text, full_transcript = add_transcript("")
            return {
                "transcript": display_text,
                "full_transcript": full_transcript
            }

    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"transcript": "", "error": str(e)}
        )


@router.post("/clear")
async def clear_transcripts():
    """Clear the transcript buffer (called when user clicks Clear button)."""
    clear_buffer()
    logger.info("🧹 Cleared transcript buffer")
    return {"status": "ok", "message": "Transcript buffer cleared"}

