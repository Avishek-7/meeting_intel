import uuid
import structlog
from fastapi import Request

async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response