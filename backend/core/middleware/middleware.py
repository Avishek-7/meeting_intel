from fastapi import Request
import time
import structlog
import uuid

logger = structlog.get_logger("middleware")

async def log_request_middleware(request: Request, call_next):
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    
    # Bind all context to structlog - will be automatically included in all logs via merge_contextvars
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
    )
    
    start_time = time.time()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    finally:
        duration = round(time.time() - start_time, 4)
        logger.info(
            "request_handled",
            status=status_code,
            duration=duration,
        )
        
        # Clear context after request
        structlog.contextvars.clear_contextvars()
