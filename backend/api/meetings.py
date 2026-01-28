from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.meeting import MeetingRequest, MeetingResponse
from services.meeting_service import process_meeting_transcript
from core.exceptions import ValidationError, AIServiceError, DatabaseError
from core.dependencies import get_current_user
from core.database import get_db

router = APIRouter(prefix="/meetings", tags=["Meetings"])

@router.post(
    "/analyze",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK
)
async def process_meeting(
    request: MeetingRequest, 
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await process_meeting_transcript(request.transcript, db)
    
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
    
    except DatabaseError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save meeting data."
        )
    
    except Exception:
        # Catch-all safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
