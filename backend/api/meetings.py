from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.meeting import (
    MeetingRequest,
    MeetingResponse,
    MeetingJobEnqueueResponse,
    MeetingJobStatusResponse,
    MeetingJobResult,
)
from services.meeting_service import process_meeting_transcript, enqueue_meeting_analysis_job
from services.user_service import get_or_create_user_by_email
from core.exceptions import ValidationError, AIServiceError, DatabaseError
from core.dependencies import get_current_user
from core.database import get_db
from core.queue import redis_client as queue_redis_client
from rq.job import Job
from rq.exceptions import NoSuchJobError
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
    # Validate user identity before processing
    # This must be outside the try block to avoid being masked by the generic exception handler
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available"
        )
    
    try:
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
        # Catch-all safety net - re-raise HTTPException to avoid masking auth errors
        if isinstance(Exception, HTTPException):
            raise
        logger.exception("Unexpected error during meeting processing.") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post(
    "/analyze-async",
    response_model=MeetingJobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_meeting_analysis(
    request: MeetingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        job_id = enqueue_meeting_analysis_job(request.transcript, str(user.id))
        return MeetingJobEnqueueResponse(job_id=job_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except AIServiceError as e:
        logger.exception("Queue unavailable during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception:
        logger.exception("Unexpected error while enqueueing meeting analysis.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.get(
    "/jobs/{job_id}",
    response_model=MeetingJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_meeting_job_status(job_id: str):
    if queue_redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background queue is not available.",
        )

    try:
        job = Job.fetch(job_id, connection=queue_redis_client)
    except NoSuchJobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    status_name = job.get_status()
    result_payload = None
    if job.is_finished and isinstance(job.result, dict):
        result_payload = MeetingJobResult(**job.result)

    error_message = None
    if job.is_failed:
        error_message = "Job failed."

    return MeetingJobStatusResponse(
        job_id=job.id,
        status=status_name,
        result=result_payload,
        error=error_message,
    )
