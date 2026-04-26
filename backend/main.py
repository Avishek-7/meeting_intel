from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.meetings import router as meetings_router
from api.debug import router as debug_router
from core.middleware.middleware import log_request_middleware as log_request
from core.middleware.request_context import request_context_middleware
from core.middleware.rate_limit import rate_limit_middleware
from api.auth import router as auth_router
from core.logging import configure_logging
from core.database import get_db
from core.cache import get_redis_client
from core.config import settings
import logging

# Configure logging before anything else
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MeetingIntel backend", extra={"environment": settings.ENVIRONMENT})
    yield
    logger.info("Shutting down MeetingIntel backend")


app = FastAPI(title="MeetingIntel", lifespan=lifespan)

# CORS — must be added before other middleware
_cors_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(log_request)
app.middleware("http")(request_context_middleware)


@app.get("/health", include_in_schema=False)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Deep health check — verifies database and Redis connectivity."""
    checks: dict = {}
    healthy = True

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check: database unavailable", exc_info=True)
        checks["database"] = "unavailable"
        healthy = False

    # Redis
    redis = get_redis_client()
    if redis is not None:
        try:
            redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            logger.warning("Health check: redis unavailable", exc_info=True)
            checks["redis"] = "unavailable"
            # Redis is non-critical (falls back to memory), don't mark unhealthy
    else:
        checks["redis"] = "unavailable"

    status_code = 200 if healthy else 503
    return JSONResponse(
        {"status": "healthy" if healthy else "unhealthy", "checks": checks},
        status_code=status_code,
    )
