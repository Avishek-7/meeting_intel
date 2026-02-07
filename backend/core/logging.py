import logging
import structlog
from structlog.stdlib import LoggerFactory
from rich.logging import RichHandler


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="%H:%M:%S")

    # --- stdlib logging → Rich ---
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        # datefmt="[%H:%M:%S]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_path=False,
                show_time=False,
            )
        ],
    )

    key_order = [
        "timestamp",
        "level",
        "event",
        "logger",
        "correlation_id",
        "method",
        "path",
        "user_id",
        "user_hash",
        "meeting_id",
        "model_name",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost",
    ]

    structlog.configure(
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            timestamper,
            structlog.processors.KeyValueRenderer(
                key_order=key_order,
                drop_missing=True,
            ),
        ],
    )


configure_logging()
logger = structlog.get_logger("meetingintel")
