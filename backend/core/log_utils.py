"""
Advanced logging utilities for better error tracking and debugging.

Provides:
- Structured error logging with full context and tracebacks
- Operation timing and performance tracking
- Function call logging decorator with automatic error handling
- Helper functions for consistent structured logging
"""

import asyncio
import structlog
import time
import functools
from typing import Optional, Any, Callable
from contextlib import asynccontextmanager
import traceback

logger = structlog.get_logger("meetingintel")


def log_error(
    event: str,
    error: Exception,
    context: Optional[dict] = None,
    operation: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Log an error with full context and traceback.
    
    Args:
        event: Event name (e.g., "database_error")
        error: Exception that occurred
        context: Additional context dictionary
        operation: What operation was being performed
        **kwargs: Additional fields to log
    """
    RESERVED_KEYS = {"event", "error_type", "error_message", "traceback", "operation"}
    
    log_data = {
        **(context or {}),
        **{k: v for k, v in kwargs.items() if k not in RESERVED_KEYS},
        "event": event,
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    }
    
    if operation:
        log_data["operation"] = operation
    
    logger.error(**log_data)


def log_info(
    event: str,
    context: Optional[dict] = None,
    **kwargs,
) -> None:
    """
    Log an info message with structured context.
    
    Args:
        event: Event name
        context: Context dictionary
        **kwargs: Additional fields
    """
    log_data = {"event": event, **(context or {}), **kwargs}
    logger.info(**log_data)


def log_warning(
    event: str,
    context: Optional[dict] = None,
    **kwargs,
) -> None:
    """
    Log a warning message with structured context.
    
    Args:
        event: Event name
        context: Context dictionary
        **kwargs: Additional fields
    """
    log_data = {"event": event, **(context or {}), **kwargs}
    logger.warning(**log_data)


def log_debug(
    event: str,
    context: Optional[dict] = None,
    **kwargs,
) -> None:
    """
    Log a debug message with structured context.
    
    Args:
        event: Event name
        context: Context dictionary
        **kwargs: Additional fields
    """
    log_data = {"event": event, **(context or {}), **kwargs}
    logger.debug(**log_data)


@asynccontextmanager
async def log_operation(
    operation: str,
    context: Optional[dict] = None,
    log_result: bool = True,
    **extra_context,
):
    """
    Track operation execution time and log success/failure.
    
    Usage:
        async with log_operation("fetch_user", user_id=user_id) as monitor:
            result = await db.get_user(user_id)
            monitor.result = result
    """
    start_time = time.time()
    monitor = _OperationMonitor(operation, context, log_result, extra_context)
    
    try:
        yield monitor
        duration = time.time() - start_time
        
        log_data = {
            "event": operation,
            "status": "success",
            "duration_sec": round(duration, 4),
            **(context or {}),
            **extra_context,
        }
        
        if log_result and monitor.result is not None:
            log_data["result"] = str(monitor.result)[:200]
        
        logger.info(**log_data)
        
    except Exception as e:
        duration = time.time() - start_time
        log_error(
            f"{operation}_failed",
            e,
            context={
                "operation": operation,
                "duration_sec": round(duration, 4),
                **(context or {}),
                **extra_context,
            }
        )
        raise


class _OperationMonitor:
    """Helper class for tracking operation results."""
    def __init__(self, op, ctx, log_result, extra):
        self.operation = op
        self.context = ctx
        self.log_result = log_result
        self.extra = extra
        self.result = None


def log_function_call(func: Callable) -> Callable:
    """
    Decorator to automatically log function calls with timing.
    
    Usage:
        @log_function_call
        async def my_function(user_id: str):
            return result
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                "function_executed",
                function=func_name,
                duration_sec=round(duration, 4),
                status="success",
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            log_error(
                "function_error",
                e,
                operation=func_name,
                context={"duration_sec": round(duration, 4)},
            )
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                "function_executed",
                function=func_name,
                duration_sec=round(duration, 4),
                status="success",
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            log_error(
                "function_error",
                e,
                operation=func_name,
                context={"duration_sec": round(duration, 4)},
            )
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

