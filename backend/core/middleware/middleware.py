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
        query_params=str(dict(request.query_params)) if request.query_params else None,
    )
    
    start_time = time.time()
    status_code = 500
    response_size = 0

    try:
        response = await call_next(request)
        status_code = response.status_code
        response_size = response.headers.get("content-length", 0)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    except Exception as e:
        logger.error(
            "request_exception",
            error_type=e.__class__.__name__,
            error_message=str(e),
            status=500,
        )
        raise

    finally:
        duration = round(time.time() - start_time, 4)
        
        # Log response with status indicator
        log_level = "info" if 200 <= status_code < 400 else "warning" if status_code < 500 else "error"
        
        log_data = {
            "event": "http_request",
            "status": status_code,
            "duration_sec": duration,
            "response_size_bytes": response_size,
        }
        
        if log_level == "info":
            logger.info(**log_data)
        elif log_level == "warning":
            logger.warning(**log_data)
        else:
            logger.error(**log_data)
        
        # Clear context after request
        structlog.contextvars.clear_contextvars()
