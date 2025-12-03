# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import config and routers
from config import init_openai_client
from routers import ingest, generate, stt, health

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
    
    # Initialize OpenAI client
    init_openai_client()
    
    yield
    
    logger.info("🛑 Server shutting down...")

# ---------------------------
# Create FastAPI app
# ---------------------------
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
# Include routers
# ---------------------------
app.include_router(ingest.router)
app.include_router(generate.router)
app.include_router(stt.router)
app.include_router(health.router)

# ---------------------------
# Run server
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
