# server/routers/generate.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import logging

import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("")
async def generate(payload: dict):
    """Generate a non-streaming answer."""
    chain = config.chain
    
    transcript = payload.get("transcript", "").strip()

    if chain is None:
        return {"status": "error", "message": "Chain not initialized. Upload your resume via /ingest first."}

    try:
        result = chain.invoke({"question": transcript, "chat_history": []})
        answer = result.get("answer") or result.get("text") or ""
        if not answer:
            return {"status": "error", "message": "Chain returned no answer"}
        return {"status": "ok", "answer": answer}
    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/stream")
async def generate_stream(payload: dict):
    """Generate a streaming answer."""
    generator_chain = config.generator_chain
    
    transcript = payload.get("transcript", "").strip()
    chat_history = payload.get("chat_history", [])
    full_interview_context = payload.get("full_interview_context", "")

    if generator_chain is None:
        return StreamingResponse(
            iter(["❌ Chain not initialized. Upload resume first."]),
            media_type="text/plain"
        )

    try:
        async def streamer():
            try:
                result = generator_chain.invoke({
                    "transcript": transcript,
                    "chat_history": chat_history,
                    "full_interview_context": full_interview_context or "",
                })

                answer = result.get("answer") or result.get("text") or ""

                if not answer:
                    yield "⚠️ No answer generated."
                    return

                words = answer.split()
                for i, word in enumerate(words):
                    yield word + (" " if i < len(words) - 1 else "")
                    await asyncio.sleep(0.02)

            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield f"❌ Error: {str(e)}"

        return StreamingResponse(streamer(), media_type="text/plain")

    except Exception as e:
        logger.error(f"/generate-stream error: {e}", exc_info=True)
        return StreamingResponse(iter([f"❌ Error: {str(e)}"]), media_type="text/plain")

