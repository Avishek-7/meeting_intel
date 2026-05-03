"""
Audio transcription service using OpenAI Whisper API.
"""

import logging
from pathlib import Path
from openai import AsyncOpenAI
from core.config import settings

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

WHISPER_MODEL = "whisper-1"


async def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribe an audio file using OpenAI Whisper.

    Args:
        audio_path: Local filesystem path only. For S3/raw bytes use
            transcribe_audio_bytes.

    Returns:
        Transcribed text string.

    Raises:
        RuntimeError: If Whisper API call fails.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Transcribing audio", extra={"bytes": path.stat().st_size})
    try:
        with open(path, "rb") as f:
            response = await _client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=f,
                response_format="text",
            )
        transcript = response if isinstance(response, str) else response.text
        logger.info("Transcription complete", extra={"chars": len(transcript)})
        return transcript
    except Exception as exc:
        logger.error("Whisper transcription failed", exc_info=True)
        raise RuntimeError(f"Transcription failed: {exc}") from exc


async def transcribe_audio_bytes(data: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe raw audio bytes (e.g. read from S3)."""
    import io
    try:
        response = await _client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=(filename, io.BytesIO(data)),
            response_format="text",
        )
        return response if isinstance(response, str) else response.text
    except Exception as exc:
        logger.error("Whisper transcription failed", exc_info=True)
        raise RuntimeError(f"Transcription failed: {exc}") from exc
