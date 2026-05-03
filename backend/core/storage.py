"""
Storage abstraction for audio file uploads.

Supports local disk storage today; swap to S3-compatible storage by setting
STORAGE_BACKEND=s3 and providing S3_BUCKET / AWS_* env vars.
"""

import os
import uuid
import logging
from pathlib import Path
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
_BACKEND = os.environ.get("STORAGE_BACKEND", "local").lower()
_LOCAL_DIR = Path(os.environ.get("STORAGE_LOCAL_DIR", "/tmp/meetingintel/audio"))

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "video/mp4",   # WhatsApp / Zoom export
    "video/webm",
}
MAX_AUDIO_BYTES = int(os.environ.get("MAX_AUDIO_BYTES", 200 * 1024 * 1024))  # 200 MB


# ── Public API ─────────────────────────────────────────────────────────────────

async def save_audio_upload(upload: UploadFile, user_id: str) -> str:
    """
    Persist an uploaded audio file and return its storage path/key.

    Args:
        upload: The FastAPI UploadFile from the HTTP request.
        user_id: Owning user's UUID string (used for namespacing).

    Returns:
        Storage path string to persist in the database.

    Raises:
        ValueError: If the file is too large or the MIME type is not allowed.
    """
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type '{content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_AUDIO_MIME_TYPES))}"
        )

    data = await upload.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"File too large ({len(data) // (1024*1024)} MB). "
            f"Maximum allowed: {MAX_AUDIO_BYTES // (1024*1024)} MB."
        )

    if _BACKEND == "s3":
        return await _save_s3(data, user_id, upload.filename or "audio", content_type)
    return _save_local(data, user_id, upload.filename or "audio")


async def read_audio_file(path: str) -> bytes:
    """Read raw bytes from a storage path returned by save_audio_upload."""
    if _BACKEND == "s3":
        return await _read_s3(path)
    return _read_local(path)


# ── Local backend ──────────────────────────────────────────────────────────────

def _save_local(data: bytes, user_id: str, filename: str) -> str:
    ext = Path(filename).suffix or ".audio"
    dest_dir = _LOCAL_DIR / user_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4()}{ext}"
    dest.write_bytes(data)
    logger.info("Audio saved locally", extra={"path": str(dest), "bytes": len(data)})
    return str(dest)


def _read_local(path: str) -> bytes:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    return p.read_bytes()


# ── S3 backend ─────────────────────────────────────────────────────────────────

async def _save_s3(data: bytes, user_id: str, filename: str, content_type: str) -> str:
    """Upload to S3-compatible storage. Requires boto3."""
    try:
        import boto3  # type: ignore
    except ImportError:
        raise RuntimeError("boto3 is required for S3 storage. Run: pip install boto3")

    bucket = os.environ["S3_BUCKET"]
    ext = Path(filename).suffix or ".audio"
    key = f"audio/{user_id}/{uuid.uuid4()}{ext}"

    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    logger.info("Audio uploaded to S3", extra={"bucket": bucket, "key": key})
    return f"s3://{bucket}/{key}"


async def _read_s3(path: str) -> bytes:
    try:
        import boto3  # type: ignore
    except ImportError:
        raise RuntimeError("boto3 is required for S3 storage. Run: pip install boto3")

    # path = "s3://bucket/key"
    without_scheme = path[len("s3://"):]
    bucket, _, key = without_scheme.partition("/")
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()
