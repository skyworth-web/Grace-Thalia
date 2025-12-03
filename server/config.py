# server/config.py

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Global chains and client
chain = None
generator_chain = None
client = None

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def check_api_key():
    """Check if OpenAI API key is set."""
    if not OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY not set. Please set it in environment variables or .env file.")
        return False
    masked = f"{OPENAI_API_KEY[:7]}...{OPENAI_API_KEY[-4:]}"
    logger.info(f"✅ OPENAI_API_KEY loaded: {masked}")
    return True

def init_openai_client():
    """Initialize OpenAI client."""
    global client
    if check_api_key():
        client = OpenAI(api_key=OPENAI_API_KEY)
        return True
    else:
        logger.warning("⚠️ OpenAI client not initialized. STT and generation endpoints will fail until API key is set.")
        return False

