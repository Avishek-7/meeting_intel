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


def infer_audio_extension(data: bytes) -> str:
    """Infer a supported audio extension from common container headers."""
    if not data:
        return "webm"

    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"fLaC"):
        return "flac"
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"ID3") or data[:2] == b"\xff\xfb":
        return "mp3"
    if len(data) > 8 and data[4:8] == b"ftyp":
        return "mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return "webm"


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
    """Transcribe raw audio bytes using a filename extension that matches the byte stream."""
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
