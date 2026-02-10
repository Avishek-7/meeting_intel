from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.meeting import (
    MeetingRequest,
    MeetingResponse,
    MeetingJobEnqueueResponse,
    MeetingJobStatusResponse,
    MeetingJobResult,
    MeetingMetadata,
    MeetingDetail,
    PaginatedMeetings,
    UserStats,
    GlobalStats,
    DailyStats,
)
from services.meeting_service import (
    process_meeting_transcript,
    enqueue_meeting_analysis_job,
    get_user_meetings,
    get_meeting_detail,
)
from services.analytics_service import (
    get_user_stats,
    get_user_daily_stats,
    get_global_stats,
    get_global_daily_stats,
    parse_date_range,
)
from services.user_service import get_or_create_user_by_email
from core.exceptions import ValidationError, AIServiceError, DatabaseError, NotFoundError
from core.dependencies import get_current_user
from core.database import get_db
from core.queue import redis_client as queue_redis_client
from rq.job import Job
from rq.exceptions import NoSuchJobError
from redis.exceptions import RedisError
from datetime import datetime
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
    
    except Exception as e:
        # Catch-all safety net - re-raise HTTPException to avoid masking auth errors
        if isinstance(e, HTTPException):
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
async def get_meeting_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

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
    except RedisError:
        logger.exception("Redis error fetching job status.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background queue is temporarily unavailable.",
        )

    email = current_user.get("email") or f"{username}@meetingintel.local"
    user = await get_or_create_user_by_email(db, email)
    job_user_id = job.meta.get("user_id") if job.meta else None
    if not job_user_id or job_user_id != str(user.id):
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


# Meeting History & Analytics Endpoints

@router.get(
    "",
    response_model=PaginatedMeetings,
    status_code=status.HTTP_200_OK,
)
async def list_user_meetings(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List user's meetings with metadata (paginated)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        meetings_data, total_count = await get_user_meetings(
            db=db,
            user_id=str(user.id),
            limit=limit,
            offset=offset
        )
        
        items = [MeetingMetadata(**m) for m in meetings_data]
        has_more = (offset + limit) < total_count
        
        return PaginatedMeetings(
            items=items,
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except DatabaseError:
        logger.exception("Database error listing meetings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meetings.",
        )
    except Exception:
        logger.exception("Unexpected error listing meetings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{meeting_id}",
    response_model=MeetingDetail,
    status_code=status.HTTP_200_OK,
)
async def get_meeting(
    meeting_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a meeting."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        meeting_data = await get_meeting_detail(
            db=db,
            user_id=str(user.id),
            meeting_id=meeting_id
        )
        
        return MeetingDetail(**meeting_data)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except DatabaseError:
        logger.exception("Database error retrieving meeting.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meeting.",
        )
    except Exception:
        logger.exception("Unexpected error retrieving meeting.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/analytics/user",
    response_model=UserStats,
    status_code=status.HTTP_200_OK,
)
async def get_user_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("today", pattern="^(today|7d|30d|all)$"),
):
    """Get user's aggregated stats."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        stats = await get_user_stats(
            db=db,
            user_id=str(user.id),
            date_from=date_from,
            date_to=date_to
        )
        
        return UserStats(**stats)
    except Exception:
        logger.exception("Error retrieving user analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics.",
        )


@router.get(
    "/analytics/user/daily",
    response_model=list[DailyStats],
    status_code=status.HTTP_200_OK,
)
async def get_user_daily_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get user's daily breakdown."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        daily_stats = await get_user_daily_stats(
            db=db,
            user_id=str(user.id),
            date_from=date_from,
            date_to=date_to
        )
        
        return [DailyStats(**stat) for stat in daily_stats]
    except Exception:
        logger.exception("Error retrieving user daily analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daily analytics.",
        )


@router.get(
    "/analytics/global",
    response_model=GlobalStats,
    status_code=status.HTTP_200_OK,
)
async def get_global_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get global stats (admin only)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    # Admin authorization check
    user_role = current_user.get("role")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        stats = await get_global_stats(
            db=db,
            date_from=date_from,
            date_to=date_to
        )
        
        return GlobalStats(**stats)
    except Exception:
        logger.exception("Error retrieving global analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global analytics.",
        )


@router.get(
    "/analytics/global/daily",
    response_model=list[DailyStats],
    status_code=status.HTTP_200_OK,
)
async def get_global_daily_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get global daily breakdown (admin only)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    # Admin authorization check
    user_role = current_user.get("role")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        daily_stats = await get_global_daily_stats(
            db=db,
            date_from=date_from,
            date_to=date_to
        )
        
        return [DailyStats(**stat) for stat in daily_stats]
    except Exception:
        logger.exception("Error retrieving global daily analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global daily analytics.",
        )
