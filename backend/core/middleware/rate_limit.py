import logging
import time
import threading
from fastapi import Request
from fastapi.responses import JSONResponse
from core.cache import get_redis_client
from core.security import verify_access_token
from core.config import settings

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

_MEMORY_LIMITS: dict[str, dict[str, int]] = {}
_MEMORY_LOCK = threading.Lock()


def _get_identifier(request: Request) -> tuple[str, bool]:
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        token = request.cookies.get(settings.AUTH_COOKIE_NAME)

    if token:
        payload = verify_access_token(token)
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}", True

    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}", False


def _redis_increment(key: str, window_seconds: int) -> int | None:
    client = get_redis_client()
    if client is None:
        return None

    try:
        pipe = client.pipeline()
        pipe.incr(key, amount=1)
        pipe.expire(key, window_seconds)
        count, _ = pipe.execute()
        return int(count)
    except Exception as exc:
        logger.warning("rate_limit_redis_failed", extra={"error": str(exc)})
        return None


def _memory_increment(key: str, window_seconds: int, now_ts: int) -> tuple[int, int]:
    window_start = now_ts - (now_ts % window_seconds)
    with _MEMORY_LOCK:
        entry = _MEMORY_LIMITS.get(key)
        if entry and entry.get("window_start") == window_start:
            entry["count"] += 1
        else:
            entry = {"window_start": window_start, "count": 1}
            _MEMORY_LIMITS[key] = entry
        return int(entry["count"]), window_start


async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in _EXEMPT_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)

    identifier, is_authenticated = _get_identifier(request)
    window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
    limit = settings.RATE_LIMIT_MAX_REQUESTS if is_authenticated else settings.RATE_LIMIT_MAX_REQUESTS_ANON

    now_ts = int(time.time())
    window_start = now_ts - (now_ts % window_seconds)
    key = f"rate_limit:{identifier}:{window_start}"

    count = _redis_increment(key, window_seconds)
    if count is None:
        count, window_start = _memory_increment(key, window_seconds, now_ts)

    if count > limit:
        retry_after = max(1, window_seconds - (now_ts - window_start))
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    return response
