"""
Add composite index for usage_records(meeting_id, created_at).

Usage:
    python -m backend.scripts.add_usage_meeting_created_index
"""

import sys
from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from backend.core.config import settings
import structlog

logger = structlog.get_logger("migrations")


def mask_db_url(db_url: str) -> str:
    try:
        parsed = urlparse(db_url)
        if parsed.password:
            masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            masked = parsed._replace(netloc=masked_netloc)
            return urlunparse(masked)
        return db_url
    except Exception:
        return "***"


def apply_index() -> bool:
    engine = None
    try:
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg"):
            db_url = db_url.replace("postgresql+asyncpg", "postgresql")

        engine = create_engine(db_url, echo=False)
        logger.info("Creating index...", url=mask_db_url(db_url))

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_usage_meeting_created "
                    "ON usage_records (meeting_id, created_at)"
                )
            )

        logger.info("Index creation complete")
        return True

    except OperationalError as exc:
        logger.error("Database connection failed", error=str(exc))
        return False
    except Exception as exc:
        logger.error("Index creation failed", error=str(exc), exc_info=True)
        return False
    finally:
        if engine is not None:
            engine.dispose()


def main() -> None:
    success = apply_index()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
