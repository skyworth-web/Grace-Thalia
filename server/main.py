# main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize chain (will be built when first used)
chain = None

# Check and log API key status on startup
def check_api_key():
    """Check if OPENAI_API_KEY is set and test connection"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY environment variable NOT SET")
        return False

    masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
    logger.info(f"✅ OPENAI_API_KEY loaded: {masked_key}")

    try:
        import openai
        openai.api_key = api_key
        # lightweight test – list 1 model
        openai.Model.list()
        logger.info("✅ OpenAI API connection test: SUCCESS")
        return True
    except Exception as e:
        logger.warning(f"⚠️  OpenAI connection test skipped ({e})")
        return True

api_key_status = check_api_key()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Interview Co-Pilot+ Server Starting")
    logger.info("=" * 60)
    logger.info(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("🌐 Server will run on: http://0.0.0.0:8000")
    
    # Check API key status
    if api_key_status:
        logger.info("✅ Server ready - API key configured and tested")
    else:
        logger.warning("⚠️  Server starting but API key not configured or invalid")
        logger.warning("   Some features will not work until API key is set")
    
    logger.info("=" * 60)
    
    yield  # Server runs here
    
    # Shutdown (if needed in the future)
    logger.info("🛑 Server shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestPayload(BaseModel):
    resume: str
    job: Optional[str] = ""  # Optional job description

@app.post("/ingest")
async def ingest(payload: IngestPayload):
    """Ingest resume and job description into vector store"""
    try:
        logger.info("📥 Received ingest request")
        
        # Check if API key is set in environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("❌ Ingest failed: OPENAI_API_KEY not set")
            return {
                "status": "error",
                "message": "OPENAI_API_KEY environment variable not set. Please set it in your server environment."
            }
        
        logger.info("✅ API key verified for ingest")
        
        # Ensure data directory exists
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Save resume
        resume_path = os.path.join(data_dir, "resume.txt")
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(payload.resume)
        logger.info(f"💾 Saved resume ({len(payload.resume)} characters)")
        
        # Save job description if provided
        if payload.job and payload.job.strip():
            job_path = os.path.join(data_dir, "job.txt")
            with open(job_path, "w", encoding="utf-8") as f:
                f.write(payload.job)
            logger.info(f"💾 Saved job description ({len(payload.job)} characters)")
        else:
            # Create empty job file if not provided
            with open(os.path.join(data_dir, "job.txt"), "w", encoding="utf-8") as f:
                f.write("")
            logger.info("💾 No job description provided, using empty file")
        
        # Ingest documents into vector store
        logger.info("🔄 Starting document ingestion into vector store...")
        ingest_docs()
        logger.info("✅ Document ingestion completed")
        
        # Rebuild chain with new data
        logger.info("🔄 Building retrieval chain...")
        global chain
        chain = build_chain()
        logger.info("✅ Retrieval chain built successfully")
        
        return {"status": "ok", "message": "Documents ingested successfully"}
    except Exception as e:
        logger.error(f"❌ Ingest error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.websocket("/stream")
async def stream(ws: WebSocket):
    """WebSocket endpoint for streaming interview suggestions"""
    await ws.accept()
    logger.info("🔌 WebSocket connection established")
    
    # Check API key status
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
        logger.info(f"✅ Using API key: {masked_key}")
    else:
        logger.error("❌ OPENAI_API_KEY not set for WebSocket connection")
        await ws.send_text(json.dumps({
            "type": "error",
            "message": "OPENAI_API_KEY not configured on server"
        }))
        await ws.close()
        return
    
    chat_history = []
    
    try:
        # Initialize chain if not already done
        global chain
        if chain is None:
            logger.info("🔄 Initializing retrieval chain for WebSocket...")
            try:
                chain = build_chain()
                logger.info("✅ Retrieval chain initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize chain: {str(e)}")
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": f"Failed to initialize chain: {str(e)}. Please ingest documents first."
                }))
                await ws.close()
                return
        
        while True:
            try:
                # Receive message from client
                data = await ws.receive_text()
                message = json.loads(data)
                
                # Handle caption text
                if message.get("type") == "caption":
                    question = message.get("text", "")
                    if not question or len(question.strip()) < 10:
                        continue
                    
                    logger.info(f"💬 Received question: {question[:50]}...")
                    try:
                        # Get suggestion from chain
                        logger.info("🔄 Processing question with AI chain...")
                        result = chain.invoke({
                            "question": question,
                            "chat_history": chat_history
                        })
                        
                        answer = result.get("answer", "")
                        
                        if answer:
                            logger.info(f"✅ Generated answer ({len(answer)} characters)")
                            # Stream the answer in chunks for better UX
                            words = answer.split()
                            chunk_size = 5
                            
                            for i in range(0, len(words), chunk_size):
                                chunk = " ".join(words[i:i + chunk_size]) + " "
                                await ws.send_text(json.dumps({
                                    "type": "suggestion",
                                    "text": chunk
                                }))
                                await asyncio.sleep(0.1)  # Small delay for streaming effect
                            
                            # Update chat history
                            chat_history.append((question, answer))
                            
                            # Keep chat history manageable (last 10 exchanges)
                            if len(chat_history) > 10:
                                chat_history = chat_history[-10:]
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing question: {str(e)}")
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": f"Error processing question: {str(e)}"
                        }))
                
            except json.JSONDecodeError:
                # Handle plain text (backward compatibility)
                question = data
                if question and len(question.strip()) >= 10:
                    try:
                        result = chain.invoke({
                            "question": question,
                            "chat_history": chat_history
                        })
                        answer = result.get("answer", "")
                        if answer:
                            await ws.send_text(json.dumps({
                                "type": "suggestion",
                                "text": answer
                            }))
                            chat_history.append((question, answer))
                            if len(chat_history) > 10:
                                chat_history = chat_history[-10:]
                    except Exception as e:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": str(e)
                        }))
    
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket client disconnected")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        try:
            await ws.close()
            logger.info("🔌 WebSocket connection closed")
        except:
            pass

generator_chain = None
@app.post("/generate")
async def generate(payload: dict):
    global generator_chain
    transcript = payload.get("transcript", "")

    if not transcript.strip():
        return {"status": "error", "message": "Transcript is empty"}

    try:
        if generator_chain is None:
            generator_chain = build_generator_chain()

        result = generator_chain({"transcript": transcript})
        answer = result["result"]

        return {
            "status": "ok",
            "answer": answer
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    """Health check endpoint"""
    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "ok",
        "api_key_configured": api_key_set,
        "chain_initialized": chain is not None
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
