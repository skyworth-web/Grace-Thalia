import requests
import aiohttp
import asyncio
import logging

BACKEND_URL = "http://localhost:8000"

class APIClient:
    def __init__(self):
        self.session = requests.Session()  # Reuse session for performance in sync requests
        self.logger = logging.getLogger(__name__)

    def ingest(self, resume, jd):
        """Ingest resume and job description to backend"""
        payload = {"resume": resume, "job": jd}
        try:
            r = self.session.post(f"{BACKEND_URL}/ingest", json=payload)
            r.raise_for_status()  # Will raise an HTTPError if status code is not 2xx
            return r.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ingest error: {e}")
            return {"status": "error", "message": str(e)}

    def generate(self, transcript):
        """Generate a response based on the transcript"""
        payload = {"transcript": transcript}
        try:
            r = self.session.post(f"{BACKEND_URL}/generate", json=payload)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Generate error: {e}")
            return {"status": "error", "message": str(e)}

    async def stream_answer(self, transcript):
        """Stream the answer from backend as the response is being generated"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{BACKEND_URL}/generate-stream", json={"transcript": transcript}) as resp:
                    resp.raise_for_status()  # Check for errors
                    async for chunk in resp.content.iter_chunked(32):
                        yield chunk.decode()  # Decode bytes and yield the response chunk by chunk
            except aiohttp.ClientError as e:
                self.logger.error(f"Stream error: {e}")
                yield f"❌ Error: {str(e)}"

    def stt(self, audio_bytes):
        """Send audio bytes to backend for Speech-to-Text processing"""
        files = {"file": ("speech.wav", audio_bytes, "audio/wav")}
        try:
            r = self.session.post(f"{BACKEND_URL}/stt", files=files)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"STT error: {e}")
            return {"transcript": "", "error": str(e)}
