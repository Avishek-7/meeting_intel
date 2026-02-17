import uuid
import re
import structlog
from fastapi import Request

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

async def request_context_middleware(request: Request, call_next):
    """Set up request context for structured logging."""
    header_value = request.headers.get("X-Request-ID")
    if header_value and _REQUEST_ID_PATTERN.match(header_value):
        request_id = header_value
    else:
        request_id = str(uuid.uuid4())

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()
