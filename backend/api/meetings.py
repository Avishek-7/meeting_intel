from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.meeting import MeetingRequest, MeetingResponse
from services.meeting_service import process_meeting_transcript
from services.user_service import get_or_create_user_by_email
from core.exceptions import ValidationError, AIServiceError, DatabaseError
from core.dependencies import get_current_user
from core.database import get_db
import logging

logger = logging.getLogger(__name__)

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
        # Get or create database user from authenticated username
        username = current_user.get("username")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User identification not available"
            )
        
        # Use email as username@domain or just username if no email available
        # In future, JWT token should contain email or user UUID
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        return await process_meeting_transcript(request.transcript, db, str(user.id))
    
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    
    except AIServiceError:
        logger.exception("AI service error during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meeting processing service is currently unavailable."
        )
    
    except DatabaseError:
        logger.exception("Database error during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save meeting data."
        )
    
    except Exception:
        # Catch-all safety net
        logger.exception("Unexpected error during meeting processing.") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
