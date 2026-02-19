from fastapi import FastAPI
from api.meetings import router as meetings_router
from api.debug import router as debug_router
from core.middleware.middleware import log_request_middleware as log_request
from core.middleware.request_context import request_context_middleware
from core.middleware.rate_limit import rate_limit_middleware
from api.auth import router as auth_router
from core.logging import configure_logging
import uvicorn

# Configure logging before anything else
configure_logging()

app = FastAPI(title="MeetingIntel")

app.include_router(meetings_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(log_request)
app.middleware("http")(request_context_middleware)


@app.get("/health")
def health_check():
    return {"status": "ok"}
