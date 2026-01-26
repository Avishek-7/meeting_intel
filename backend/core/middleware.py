from fastapi import Request
from core.logging import logger
import time

async def log_request(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    duration = round(time.time() - start_time, 4)
    logger.info(
        "Request handled",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration": duration
        }
    )
    return response