from core.exceptions import ValidationError, AIServiceError, DatabaseError
from ai_engine.pipeline import analyze_meeting
from schemas.meeting import MeetingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, func, and_
from typing import Tuple, Dict
from models.meeting import Meeting
from models.usage_record import UsageRecord
from core.cache import get_redis_client
from core.cache_keys import meeting_cache_key
from core.cache_invalidation import invalidate_meeting_cache
from services.usage_service import track_ai_usage
from core.queue import default_queue
import json
import structlog
import time
from core.transcript import generate_transcript_hash
import uuid

logger = structlog.get_logger("services.meeting_service")
redis_client = get_redis_client()

CACHE_TTL_SECONDS = 60 * 10 # 10 minutes

def enqueue_meeting_analysis_job(transcript: str, user_id: str) -> str:
    if default_queue is None:
        logger.error("queue_unavailable")
        raise AIServiceError("Background queue is not available.")

    # Validate user_id format early
    try:
        uuid.UUID(user_id)
    except (ValueError, TypeError) as e:
        logger.warning("invalid_user_id_format")
        raise ValidationError("Invalid user_id format.") from e

    if len(transcript) < 10:
        logger.warning("transcript_too_short")
        raise ValidationError("Transcript is too short to process.")

    job = default_queue.enqueue(
        "jobs.meeting_analysis.run_meeting_analysis_job_sync",
        transcript,
        user_id,
        job_timeout=300,
    )
    try:
        job.meta["user_id"] = user_id
        job.save_meta()
    except Exception as e:
        logger.warning("job_meta_save_failed", job_id=job.id, error=str(e))
        try:
            job.cancel()
        except Exception:
            logger.error("job_cancel_failed", job_id=job.id)
        raise AIServiceError("Failed to enqueue meeting analysis job.") from e
    logger.info("meeting_analysis_job_enqueued", job_id=job.id)
    return job.id

def _validate_ai_result(result: dict) -> None:
    if not isinstance(result, dict):
        logger.error("AI service returned non-dict response.")
        raise AIServiceError("AI service returned invalid response.")

    if "summary" not in result or "action_items" not in result:
        logger.error("AI response missing required fields.")
        raise AIServiceError("AI response missing required fields.")

async def process_meeting_transcript(
        transcript: str,
        db: AsyncSession,
        user_id: str
) -> MeetingResponse:
    """
    Handles meeting transcript processing.
    Business logic lives here, not in routes.
    """
    start_time = time.perf_counter()
    logger.info("process_meeting_start", transcript_length=len(transcript), user_id=user_id)
    
    # Validate user_id format early
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError) as e:
        logger.warning("invalid_user_id_format", user_id=user_id)
        raise ValidationError("Invalid user_id format.") from e
    
    # Business rule validation
    if len(transcript) < 10:
        logger.warning("transcript_too_short")
        raise ValidationError("Transcript is too short to process.")

    cache_key = meeting_cache_key(transcript)

    cached_result = None
    cache_get_start = time.perf_counter()
    if redis_client is not None:
        try:
            cached_result = redis_client.get(cache_key)
            cache_get_duration = time.perf_counter() - cache_get_start
            logger.info("cache_get_complete", duration_seconds=round(cache_get_duration, 3))
        except Exception as e:
            cache_get_duration = time.perf_counter() - cache_get_start
            logger.error("cache_get_failed", duration_seconds=round(cache_get_duration, 3), error=str(e))

    from_cache = False
    if cached_result:
        logger.info("cache_hit")
        try:
            result = json.loads(cached_result)
        except (TypeError, ValueError) as e:
            logger.error("cache_decode_failed", error=str(e))
            raise AIServiceError("Cached AI response is corrupted.") from e

        try:
            _validate_ai_result(result)
        except AIServiceError as e:
            logger.error("cache_validation_failed")
            raise AIServiceError("Cached AI response is corrupted.") from e
        from_cache = True

    else:
        logger.info("cache_miss")
        ai_start = time.perf_counter()
        result = await run_in_threadpool(analyze_meeting, transcript)
        ai_duration = time.perf_counter() - ai_start
        logger.info("ai_analysis_complete", duration_seconds=round(ai_duration, 3))
        _validate_ai_result(result)

        if redis_client is not None:
            cache_set_start = time.perf_counter()
            try:
                redis_client.setex(
                    cache_key,
                    CACHE_TTL_SECONDS,
                    json.dumps(result)
                )
                cache_set_duration = time.perf_counter() - cache_set_start
                logger.info("cache_set_complete", duration_seconds=round(cache_set_duration, 3), ttl_seconds=CACHE_TTL_SECONDS)
            except Exception as e:
                cache_set_duration = time.perf_counter() - cache_set_start
                logger.error("cache_set_failed", duration_seconds=round(cache_set_duration, 3), error=str(e))
    
    # Calculate transcript hash for deduplication
    transcript_hash = generate_transcript_hash(transcript)
    
    logger.info("checking_existing_meeting")
    db_check_start = time.perf_counter()
    existing = await db.execute(
        select(Meeting.id).where(Meeting.transcript_hash == transcript_hash)
    )
    db_check_duration = time.perf_counter() - db_check_start
    logger.info("db_check_complete", duration_seconds=round(db_check_duration, 3))
    
    existing_meeting_id = existing.scalar_one_or_none()
    if existing_meeting_id is not None:
        logger.info("meeting_already_persisted")
        return MeetingResponse(
            summary=result["summary"],
            action_items=result["action_items"],
        )

    try:
        logger.info("persisting_meeting_data")
        db_write_start = time.perf_counter()

        meeting = Meeting(
            id=uuid.uuid4(),
            user_id=user_uuid,
            transcript_text=transcript,
            transcript_hash=transcript_hash,
            summary_text=result["summary"],
            action_items=result["action_items"]
        )
        db.add(meeting)
        await db.flush()
        await db.commit()

        db_write_duration = time.perf_counter() - db_write_start
        logger.info("meeting_persisted", duration_seconds=round(db_write_duration, 3))

        # Track AI usage if token info is available in result
        if "usage" in result and not from_cache:
            try:
                usage_info = result["usage"]
                await track_ai_usage(
                    db=db,
                    user_id=user_uuid,
                    meeting_id=meeting.id,
                    model_name=usage_info.get("model", "unknown"),
                    prompt_tokens=usage_info.get("prompt_tokens", 0),
                    completion_tokens=usage_info.get("completion_tokens", 0)
                )
            except Exception as e:
                logger.warning("track_usage_failed", error=str(e))

        invalidate_meeting_cache(transcript)
    except IntegrityError as e:
        logger.warning("concurrent_insert_detected")
        await db.rollback()
        existing = await db.execute(
            select(Meeting.id).where(Meeting.transcript_hash == transcript_hash)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("concurrent_insert_resolved")
            return MeetingResponse(
                summary=result["summary"],
                action_items=result["action_items"],
            )
        raise DatabaseError("Failed to persist meeting data.") from e
    except SQLAlchemyError as e:
        logger.error("database_error_persist_meeting", error=str(e))
        await db.rollback()
        raise DatabaseError("Failed to persist meeting data.") from e

    total_duration = time.perf_counter() - start_time
    logger.info("process_meeting_complete", duration_seconds=round(total_duration, 3), from_cache=from_cache)
    
    return MeetingResponse(
        summary=result["summary"],
        action_items=result["action_items"],
    )


async def get_user_meetings(
    db: AsyncSession,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> Tuple[list, int]:
    """
    Get paginated list of user's meetings with metadata.
    
    Args:
        db: Database session
        user_id: UUID of the user
        limit: Number of results per page
        offset: Pagination offset
    
    Returns:
        Tuple of (meetings_metadata_list, total_count)
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError) as e:
        logger.warning("invalid_user_id_format_history", user_id=user_id)
        raise ValidationError("Invalid user_id format.") from e
    
    try:
        # Get total count
        count_result = await db.execute(
            select(func.count(Meeting.id)).where(Meeting.user_id == user_uuid)
        )
        total_count = count_result.scalar() or 0
        
        # Get paginated meetings
        result = await db.execute(
            select(Meeting).where(Meeting.user_id == user_uuid)
            .order_by(Meeting.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        meetings = result.scalars().all()
        meetings_data = []
        
        for meeting in meetings:
            # Get usage info for this meeting
            usage_result = await db.execute(
                select(func.sum(UsageRecord.total_tokens), func.sum(UsageRecord.estimated_cost)).where(
                    UsageRecord.meeting_id == meeting.id
                )
            )
            tokens, cost = usage_result.first()
            
            # Create preview (first 200 chars of summary)
            summary_preview = meeting.summary_text[:200] if meeting.summary_text else ""
            
            action_count = len(meeting.action_items) if isinstance(meeting.action_items, list) else 0
            
            meetings_data.append({
                "id": str(meeting.id),
                "created_at": meeting.created_at,
                "summary_preview": summary_preview,
                "action_count": action_count,
                "total_tokens": tokens or 0,
                "estimated_cost": cost or 0
            })
        
        logger.info("user_meetings_retrieved", user_id=str(user_uuid)[:8], count=len(meetings_data))
        return meetings_data, total_count
        
    except Exception as e:
        logger.error("get_user_meetings_failed", error=str(e))
        raise DatabaseError("Failed to retrieve user meetings.") from e


async def get_meeting_detail(
    db: AsyncSession,
    user_id: str,
    meeting_id: str
) -> Dict:
    """
    Get full details of a meeting (with authorization check).
    
    Args:
        db: Database session
        user_id: UUID of the user (for authorization)
        meeting_id: UUID of the meeting
    
    Returns:
        Meeting detail dict with summary, action items, usage info
    """
    try:
        user_uuid = uuid.UUID(user_id)
        meeting_uuid = uuid.UUID(meeting_id)
    except (ValueError, TypeError) as e:
        logger.warning("invalid_uuid_format_detail")
        raise ValidationError("Invalid UUID format.") from e
    
    try:
        result = await db.execute(
            select(Meeting).where(
                and_(
                    Meeting.id == meeting_uuid,
                    Meeting.user_id == user_uuid
                )
            )
        )
        
        meeting = result.scalar_one_or_none()
        if meeting is None:
            logger.warning("meeting_not_found", meeting_id=str(meeting_uuid)[:8], user_id=str(user_uuid)[:8])
            raise ValueError("Meeting not found or access denied.")
        
        # Get usage info
        usage_result = await db.execute(
            select(UsageRecord).where(UsageRecord.meeting_id == meeting.id)
        )
        usage_record = usage_result.scalar_one_or_none()
        
        return {
            "id": str(meeting.id),
            "created_at": meeting.created_at,
            "summary": meeting.summary_text,
            "action_items": meeting.action_items or [],
            "total_tokens": usage_record.total_tokens if usage_record else 0,
            "estimated_cost": usage_record.estimated_cost if usage_record else 0,
            "model_name": usage_record.model_name if usage_record else None,
            "prompt_tokens": usage_record.prompt_tokens if usage_record else 0,
            "completion_tokens": usage_record.completion_tokens if usage_record else 0
        }
        
    except Exception as e:
        logger.error("get_meeting_detail_failed", error=str(e))
        raise DatabaseError("Failed to retrieve meeting details.") from e
