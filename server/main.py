# main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from chains.retrieval_chain import ingest_docs, build_chain
from chains.generator_chain import build_generator_chain
import os
import json
import asyncio
import logging
from datetime import datetime

# ---------------------------
# Logging
# ---------------------------
# Load .env if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------
# Global chains and client
# ---------------------------
chain = None
generator_chain = None
client = None

# ---------------------------
# OpenAI client setup
# ---------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def check_api_key():
    if not OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY not set. Please set it in environment variables or .env file.")
        return False
    masked = f"{OPENAI_API_KEY[:7]}...{OPENAI_API_KEY[-4:]}"
    logger.info(f"✅ OPENAI_API_KEY loaded: {masked}")
    return True

if check_api_key():
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("⚠️ OpenAI client not initialized. STT and generation endpoints will fail until API key is set.")

# ---------------------------
# FastAPI Lifespan
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*60)
    logger.info("🚀 Interview Co-Pilot+ Server Starting")
    logger.info("="*60)
    logger.info(f"📅 Started at {datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info("🌐 Running on http://0.0.0.0:8000")
    logger.info("="*60)
    yield
    logger.info("🛑 Server shutting down...")

app = FastAPI(lifespan=lifespan)

# ---------------------------
# CORS
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Ingest endpoint
# ---------------------------
class IngestPayload(BaseModel):
    resume: str
    job: Optional[str] = ""

@app.post("/ingest")
async def ingest(payload: IngestPayload):
    global chain, generator_chain
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)

        # Save resume and job
        with open(os.path.join(data_dir, "resume.txt"), "w", encoding="utf-8") as f:
            f.write(payload.resume)
        with open(os.path.join(data_dir, "job.txt"), "w", encoding="utf-8") as f:
            f.write(payload.job or "")

        # Ingest documents and build chains
        ingest_docs()
        chain = build_chain()
        generator_chain = build_generator_chain()

        return {"status": "ok", "message": "Documents ingested and chains initialized"}

    except Exception as e:
        logger.error(f"Ingest error: {e}")
        return {"status": "error", "message": str(e)}

# ---------------------------
# Generate final answer (non-stream)
# ---------------------------
@app.post("/generate")
async def generate(payload: dict):
    global chain
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
        logger.error(f"/generate error: {str(e)}")
        return {"status": "error", "message": str(e)}

# ---------------------------
# Streaming generation
# ---------------------------
from fastapi.responses import StreamingResponse

@app.post("/generate-stream")
async def generate_stream(payload: dict):
    global generator_chain
    transcript = payload.get("transcript", "").strip()

    if generator_chain is None:
        return StreamingResponse(
            iter(["❌ Chain not initialized. Upload resume first."]),
            media_type="text/plain"
        )

    try:
        result = generator_chain.invoke({"transcript": transcript})
        answer = result.get("answer") or result.get("text") or ""

        async def streamer():
            words = answer.split()
            for i in range(0, len(words), 5):
                chunk = " ".join(words[i:i+5]) + " "
                yield chunk
                await asyncio.sleep(0.05)

        return StreamingResponse(streamer(), media_type="text/plain")
    except Exception as e:
        return StreamingResponse(
            iter([f"❌ Error: {str(e)}"]),
            media_type="text/plain"
        )

# ---------------------------
# Health check
# ---------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "api_key": bool(OPENAI_API_KEY),
        "chain_initialized": chain is not None
    }

# ---------------------------
# STT - speech to text
# ---------------------------
@app.post("/stt")
async def stt(file: UploadFile = File(...)):
    if client is None:
        return {"transcript": "", "error": "OpenAI client not initialized. Set OPENAI_API_KEY."}
    try:
        audio_bytes = await file.read()
        logger.info(f"🎤 STT received file {file.filename} ({file.content_type})")
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename, audio_bytes, file.content_type)
        )
        return {"transcript": result.text or ""}
    except Exception as e:
        logger.error(f"STT error: {e}")
        return {"transcript": "", "error": str(e)}

# ---------------------------
# Run server
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
