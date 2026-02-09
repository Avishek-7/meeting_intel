"""
Migration helper to apply schema changes.

This script creates/updates database tables with the new indices and relationships.
Run this after deploying model changes.

Usage:
    python -m backend.scripts.apply_migrations
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from core.config import settings
from models.base import Base
import structlog

logger = structlog.get_logger("migrations")


def apply_migrations():
    """Apply pending migrations by creating/updating tables."""
    try:
        # Convert async URL to sync URL for migrations
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg"):
            db_url = db_url.replace("postgresql+asyncpg", "postgresql")
        elif not db_url.startswith("postgresql"):
            # Already on psycopg2 or other sync driver
            pass
        
        engine = create_engine(
            db_url,
            echo=False,
        )
        
        logger.info("Applying migrations...", url=db_url[:50])
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        
        # Create all tables with their current schema
        # This is safe to run multiple times; SQLAlchemy skips existing tables
        with engine.begin() as conn:
            Base.metadata.create_all(conn)
            logger.info("Schema creation complete")
            
            # Log created/updated tables
            result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            tables = result.fetchall()
            table_names = [t[0] for t in tables]
            logger.info("Current tables", count=len(table_names), tables=table_names)
        
        logger.info("✓ Migration complete")
        engine.dispose()
        return True
        
    except OperationalError as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        return False


def main():
    """CLI entry point."""
    success = apply_migrations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
