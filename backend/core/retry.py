import asyncio
import structlog

logger = structlog.get_logger("core.retry")

async def retry_async(
        func,
        retries: int = 3,
        delay: float = 1.0,
):
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