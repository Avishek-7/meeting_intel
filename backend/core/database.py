from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine 
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from core.config import settings
import logging

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)

def get_sync_db():
    """Return a synchronous database session."""
    return SyncSessionLocal()

def _get_async_db_url(sync_url: str) -> str:
    """Convert sync database URL to async database URL."""
    scheme = sync_url.split(":", 1)[0] if sync_url else "unknown"
    logger.debug("Converting database URL to async driver (scheme=%s).", scheme)
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://")
    elif sync_url.startswith("postgres://"):
        return sync_url.replace("postgres://", "postgresql+asyncpg://")
    elif sync_url.startswith("postgresql+psycopg2://"):
        return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    elif sync_url.startswith("postgresql+psycopg://"):
        return sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    else:
        raise ValueError("Unsupported database URL scheme for async conversion.")

async_database_url = _get_async_db_url(settings.DATABASE_URL)
async_engine = create_async_engine(async_database_url, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

# Import models to register them with SQLAlchemy
from models import Meeting as _Meeting, User as _User, UsageRecord as _UsageRecord  # noqa: E402,F401

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    logger.debug("Opening async database session.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError:
            logger.error("Database error during session.", exc_info=True)
            raise
        finally:
            logger.debug("Closing async database session.")
