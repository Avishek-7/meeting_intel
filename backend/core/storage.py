"""
Storage abstraction for audio file uploads.

Supports local disk storage today; swap to S3-compatible storage by setting
STORAGE_BACKEND=s3 and providing S3_BUCKET / AWS_* env vars.
"""

import asyncio
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

    content_length_header = upload.headers.get("content-length") if upload.headers else None
    if content_length_header:
        try:
            declared_size = int(content_length_header)
        except ValueError:
            declared_size = None
        if declared_size is not None and declared_size > MAX_AUDIO_BYTES:
            raise ValueError(
                f"File too large ({declared_size // (1024*1024)} MB). "
                f"Maximum allowed: {MAX_AUDIO_BYTES // (1024*1024)} MB."
            )

    chunk_size = 1024 * 1024
    total_size = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_AUDIO_BYTES:
            raise ValueError(
                f"File too large ({total_size // (1024*1024)} MB). "
                f"Maximum allowed: {MAX_AUDIO_BYTES // (1024*1024)} MB."
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if total_size > MAX_AUDIO_BYTES:
        raise ValueError(
            f"File too large ({total_size // (1024*1024)} MB). "
            f"Maximum allowed: {MAX_AUDIO_BYTES // (1024*1024)} MB."
        )

    if _BACKEND == "s3":
        return await _save_s3(data, user_id, upload.filename or "audio", content_type)
    dest = _save_local(user_id, upload.filename or "audio")
    await asyncio.to_thread(dest.write_bytes, data)
    logger.info("Audio saved locally", extra={"path": str(dest), "bytes": len(data)})
    return str(dest)


async def read_audio_file(path: str) -> bytes:
    """Read raw bytes from a storage path returned by save_audio_upload."""
    if _BACKEND == "s3":
        return await _read_s3(path)
    return await asyncio.to_thread(_read_local, path)


# ── Local backend ──────────────────────────────────────────────────────────────

def _save_local(user_id: str, filename: str) -> Path:
    user_segment = (user_id or "").strip()
    if not user_segment or "/" in user_segment or "\\" in user_segment or ".." in user_segment:
        raise ValueError("Invalid user identifier for storage path")

    ext = Path(filename).suffix or ".audio"
    dest_dir = _LOCAL_DIR / Path(user_segment).name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4()}{ext}"
    return dest


def _read_local(path: str) -> bytes:
    root = _LOCAL_DIR.resolve()
    p = Path(path).resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise FileNotFoundError("Audio file path is outside configured storage directory") from exc

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

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable not set")

    ext = Path(filename).suffix or ".audio"
    key = f"audio/{user_id}/{uuid.uuid4()}{ext}"

    s3 = boto3.client("s3")
    await asyncio.to_thread(
        s3.put_object,
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
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
    configured_bucket = os.environ.get("S3_BUCKET")
    if configured_bucket and bucket and bucket != configured_bucket:
        raise RuntimeError("S3 path bucket does not match configured S3_BUCKET")
    if not bucket:
        bucket = configured_bucket or ""
    if not bucket:
        raise RuntimeError("S3 bucket not provided and S3_BUCKET is not set")

    s3 = boto3.client("s3")
    response = await asyncio.to_thread(s3.get_object, Bucket=bucket, Key=key)
    return await asyncio.to_thread(response["Body"].read)
