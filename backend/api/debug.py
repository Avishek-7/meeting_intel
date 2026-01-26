from fastapi import APIRouter, Request 

router = APIRouter(prefix="/debug", tags=["Debug"])

@router.get("/request-info")
async def get_request_info(request: Request):
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "client": request.client.host if request.client else None
    }
    