import logging
import structlog
from structlog.stdlib import LoggerFactory
from rich.logging import RichHandler


def configure_logging() -> None:
    """Configure structured logging with Rich output and context variables."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # --- stdlib logging → Rich ---
    logging.basicConfig(
        level=logging.DEBUG,  # Capture all levels, let processors filter
        format="%(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=True,  # Show local variable values in tracebacks
                show_path=True,  # Show file path and line number
                show_time=True,
                markup=True,
            )
        ],
    )

    # Define key order for consistent, readable output
    key_order = [
        "timestamp",
        "level",
        "event",
        "logger",
        "correlation_id",
        "request_id",
        "method",
        "path",
        "query_params",
        "status",
        "duration_sec",
        "response_size_bytes",
        "user_hash",  # Anonymized user identifier (never log raw user_id)
        "username",
        "operation",
        "function",
        "meeting_id",
        "error_type",
        "error_message",
        "model_name",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost",
        "cache_hit",
        "db_affected_rows",
    ]

    structlog.configure(
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
        processors=[
            structlog.stdlib.filter_by_level,  # Filter by level
            structlog.contextvars.merge_contextvars,  # Add context vars
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,  # Format exception info with traceback
            timestamper,
            structlog.processors.KeyValueRenderer(
                key_order=key_order,
                drop_missing=True,
                sort_keys=False,  # Respect key_order
            ),
        ],
    )


configure_logging()
logger = structlog.get_logger("meetingintel")
