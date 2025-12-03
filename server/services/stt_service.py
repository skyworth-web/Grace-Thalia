# server/services/stt_service.py

import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def transcribe_audio(client_instance: OpenAI, audio_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Transcribe audio using OpenAI Whisper.
    
    Args:
        client_instance: OpenAI client instance
        audio_bytes: Audio data as bytes
        filename: Original filename
        content_type: MIME type of audio
        
    Returns:
        Transcribed text or empty string on error
    """
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

