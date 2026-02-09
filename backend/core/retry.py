import asyncio
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from functools import wraps
from typing import Type, Tuple

logger = structlog.get_logger("core.retry")

async def retry_async(
        func,
        retries: int = 3,
        delay: float = 1.0,
):
    if retries < 1:
        raise ValueError("Retries must be at least 1")
    
    for attempt in range(1, retries + 1):
        try:
            return await func()
        except Exception as e:
            logger.warning(
                "retry_attempt_failed",
                attempt=attempt,
                error=str(e),
            )

            if attempt == retries:
                raise
            await asyncio.sleep(delay)


def with_exponential_backoff(
    exception_types: Tuple[Type[Exception], ...],
    max_retries: int,
    base_wait_seconds: float,
    max_wait_seconds: float = 10,
):
    """
    Decorator factory that creates a retry decorator with exponential backoff.
    
    Args:
        exception_types: Tuple of exception types to retry on
        max_retries: Maximum number of retry attempts
        base_wait_seconds: Base wait time in seconds
        max_wait_seconds: Maximum wait time between retries
    
    Returns:
        A retry decorator using tenacity with exponential backoff
    """
    return retry(
        retry=retry_if_exception_type(exception_types),
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=base_wait_seconds,
            max=max_wait_seconds,
        ),
    )