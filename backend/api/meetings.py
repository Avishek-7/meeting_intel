from fastapi import APIRouter, HTTPException, status, Depends
from schemas.meeting import MeetingRequest, MeetingResponse
from services.meeting_service import process_meeting_transcript
from core.exceptions import ValidationError, AIServiceError
from core.dependencies import get_current_user

router = APIRouter(prefix="/meetings", tags=["Meetings"])

@router.post(
    "/analyze",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK
)
async def process_meeting(request: MeetingRequest, current_user: dict = Depends(get_current_user)):
    try:
        return await process_meeting_transcript(request.transcript)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except AIServiceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meeting processing service is currently unavailable."
        )
    
    except Exception:
        # Catch-all safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
