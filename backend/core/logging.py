import logging
import sys
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
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )


configure_logging()
logger = structlog.get_logger("meetingintel")
