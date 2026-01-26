from fastapi import FastAPI
from api.meetings import router as meetings_router
from api.debug import router as debug_router
from core.middleware import log_request
from api.auth import router as auth_router
import uvicorn

app = FastAPI(title="MeetingIntel")

app.include_router(meetings_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.middleware("http")(log_request)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/authorize")
def authorize():
    return {
        "message": "Authorization endpoint placeholder",
        "hint": "Use POST /auth/login for password login"
    }
