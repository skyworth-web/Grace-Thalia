# main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager

# ⬇️ NEW IMPORT FOR REAL-TIME TRANSCRIPT STORAGE
from chains.retrieval_chain import ingest_docs, build_chain, append_transcript_chunk

from chains.generator_chain import build_generator_chain
import os
import json
import asyncio
import logging
from datetime import datetime
import sounddevice as sd

# ---------------------------
# Logging
# ---------------------------
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

        with open(os.path.join(data_dir, "resume.txt"), "w", encoding="utf-8") as f:
            f.write(payload.resume)

        with open(os.path.join(data_dir, "job.txt"), "w", encoding="utf-8") as f:
            f.write(payload.job or "")

        ingest_docs()
        chain = build_chain()
        generator_chain = build_generator_chain()

        return {"status": "ok", "message": "Documents ingested and chains initialized"}

    except Exception as e:
        logger.error(f"Ingest error: {e}")
        return {"status": "error", "message": str(e)}

# ---------------------------
# Generate final answer
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
    chat_history = payload.get("chat_history", [])
    full_interview_context = payload.get("full_interview_context", "")

    if generator_chain is None:
        return StreamingResponse(iter(["❌ Chain not initialized. Upload resume first."]), media_type="text/plain")

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

# ---------------------------
# Health check
# ---------------------------
@app.get("/health")
async def health():
    chroma_exists = os.path.exists(os.path.join(os.path.dirname(__file__), "data", "chroma"))
    doc_count = 0

    if chroma_exists:
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_chroma import Chroma
            
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            chroma = Chroma(
                persist_directory=os.path.join(os.path.dirname(__file__), "data", "chroma"),
                embedding_function=embeddings,
            )

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

# ---------------------------
# STT - speech to text
# ---------------------------
import asyncio
from concurrent.futures import ThreadPoolExecutor

stt_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="STT")

@app.post("/stt")
async def stt(file: UploadFile = File(...)):
    if client is None:
        return {"transcript": "", "error": "OpenAI client not initialized. Set OPENAI_API_KEY."}

    try:
        audio_bytes = await file.read()
        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            stt_executor,
            _transcribe_audio,
            client,
            audio_bytes,
            file.filename,
            file.content_type
        )

        if result:
            logger.info(f"📝 STT transcript: {result[:50]}...")

            # 🔥 Store transcript chunk in vector DB
            append_transcript_chunk(
                text=result,
                speaker="unknown",
                timestamp=str(datetime.now())
            )

        return {"transcript": result or ""}

    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        return {"transcript": "", "error": str(e)}

def _transcribe_audio(client_instance, audio_bytes: bytes, filename: str, content_type: str):
    try:
        result = client_instance.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, audio_bytes, content_type),
            temperature=0,
            language="en",
            prompt="Software engineer job interview conversation.",
        )

        if hasattr(result, 'text'):
            return result.text
        elif isinstance(result, dict):
            return result.get('text', '')
        return str(result) if result else ""

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        return ""

# ---------------------------
# Audio input stream
# ---------------------------
def audio_callback(indata, frames, time, status):
    if status:
        print(status)

def get_default_input_device():
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            return i
    raise RuntimeError("No input devices available")

try:
    default_device = get_default_input_device()
    with sd.InputStream(callback=audio_callback, channels=1, samplerate=16000, device=default_device):
        pass
except Exception as e:
    print(f"Error initializing audio stream: {e}")

# ---------------------------
# Run server
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
