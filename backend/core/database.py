from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine 
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

sync_engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)

def get_sync_db():
    """Return a synchronous database session."""
    return SyncSessionLocal()

def _get_async_db_url(sync_url: str) -> str:
    """Convert sync database URL to async database URL."""
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

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

