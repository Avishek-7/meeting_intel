from core.exceptions import ValidationError, AIServiceError, DatabaseError, NotFoundError
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
from core.privacy import hash_user_id, hash_meeting_id
from core.log_utils import log_error, log_info, log_warning, log_operation
import json
import structlog
import time
from core.transcript import generate_transcript_hash
import uuid

logger = structlog.get_logger("services.meeting_service")
redis_client = get_redis_client()

CACHE_TTL_SECONDS = 60 * 10 # 10 minutes

def enqueue_meeting_analysis_job(transcript: str, user_id: str) -> str:
    """
    Enqueue a meeting analysis job for async processing.
    
    Args:
        transcript: Meeting transcript text
        user_id: User UUID string
        
    Returns:
        Job ID string
        
    Note:
        user_id is passed both as a function argument (primary) and in job metadata
        (for monitoring/debugging). The function argument ensures the job has all
        required data even if metadata operations fail.
    """
    if default_queue is None:
        log_error(
            "queue_unavailable",
            Exception("RQ queue not initialized"),
            operation="enqueue_meeting_analysis"
        )
        raise AIServiceError("Background queue is not available.")

    # Validate user_id format early
    try:
        uuid.UUID(user_id)
    except (ValueError, TypeError) as e:
        log_warning(
            "invalid_user_id_format_enqueue",
            context={"user_hash": hash_user_id(user_id)},
            error_msg=str(e)
        )
        raise ValidationError("Invalid user_id format.") from e

    if len(transcript) < 10:
        log_warning(
            "transcript_too_short",
            context={"user_hash": hash_user_id(user_id), "transcript_length": len(transcript)}
        )
        raise ValidationError("Transcript is too short to process.")

    # Enqueue with metadata set atomically to avoid race condition
    # user_id is passed as both function argument (critical) and metadata (supplementary)
    try:
        job = default_queue.enqueue(
            "jobs.meeting_analysis.run_meeting_analysis_job_sync",
            transcript,
            user_id,
            job_timeout=300,
            meta={"user_id": user_id}  # Set metadata atomically during enqueue
        )
        log_info(
            "meeting_analysis_job_enqueued",
            job_id=job.id,
            user_hash=hash_user_id(user_id),
            transcript_length=len(transcript)
        )
        return job.id
    except Exception as e:
        log_error(
            "job_enqueue_failed",
            e,
            context={
                "user_hash": hash_user_id(user_id),
                "transcript_length": len(transcript)
            },
            operation="enqueue_meeting_analysis_job"
        )
        raise AIServiceError("Failed to enqueue meeting analysis job.") from e

def _validate_ai_result(result: dict) -> None:
    if not isinstance(result, dict):
        log_error(
            "ai_service_invalid_response",
            Exception("Expected dict response"),
            context={"response_type": type(result).__name__},
            operation="validate_ai_result"
        )
        raise AIServiceError("AI service returned invalid response.")

    status = result.get("status")
    if status and status != "ok":
        log_warning(
            "ai_service_partial_result",
            context={
                "status": status,
                "error_count": len(result.get("errors", [])),
            },
        )

    if "summary" not in result or "action_items" not in result:
        log_error(
            "ai_response_missing_fields",
            Exception("Missing required fields"),
            context={
                "has_summary": "summary" in result,
                "has_action_items": "action_items" in result,
                "keys": list(result.keys())
            },
            operation="validate_ai_result"
        )
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
    
    # Validate user_id format early
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError) as e:
        logger.warning("invalid_user_id_format")  # Don't log PII
        raise ValidationError("Invalid user_id format.") from e
    
    logger.info("process_meeting_start", transcript_length=len(transcript), user_hash=hash_user_id(user_uuid))
    
    # Business rule validation
    if len(transcript) < 10:
        logger.warning("transcript_too_short")
        raise ValidationError("Transcript is too short to process.")

    # Calculate transcript hash for deduplication
    transcript_hash = generate_transcript_hash(transcript)
    
    # Check database FIRST to avoid unnecessary AI processing
    logger.info("checking_existing_meeting")
    db_check_start = time.perf_counter()
    existing = await db.execute(
        select(Meeting).where(
            Meeting.transcript_hash == transcript_hash,
            Meeting.user_id == user_uuid
        )
    )
    existing_meeting = existing.scalar_one_or_none()
    db_check_duration = time.perf_counter() - db_check_start
    logger.info("db_check_complete", duration_seconds=round(db_check_duration, 3))
    
    if existing_meeting is not None:
        logger.info("meeting_already_persisted", meeting_hash=hash_meeting_id(existing_meeting.id))
        total_duration = time.perf_counter() - start_time
        logger.info("process_meeting_complete", duration_seconds=round(total_duration, 3), from_cache=True, from_db=True)
        # Return existing database record to avoid AI processing
        return MeetingResponse(
            summary=existing_meeting.summary_text,
            action_items=existing_meeting.action_items or [],
        )

    # Meeting doesn't exist - proceed with AI processing
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
            if redis_client is not None:
                try:
                    redis_client.delete(cache_key)
                except Exception as delete_error:
                    logger.error("cache_delete_failed", error=str(delete_error))
            from_cache = False
            cached_result = None
        
        if cached_result:
            try:
                _validate_ai_result(result)
            except AIServiceError as e:
                logger.error("cache_validation_failed", error=str(e))
                if redis_client is not None:
                    try:
                        redis_client.delete(cache_key)
                    except Exception as delete_error:
                        logger.error("cache_delete_failed", error=str(delete_error))
                from_cache = False
                cached_result = None
            else:
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
    
    # Meeting doesn't exist in DB - proceed to persist
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
        # Fetch the existing meeting that was inserted concurrently
        existing = await db.execute(
            select(Meeting).where(
                Meeting.transcript_hash == transcript_hash,
                Meeting.user_id == user_uuid
            )
        )
        existing_meeting = existing.scalar_one_or_none()
        if existing_meeting is not None:
            logger.info("concurrent_insert_resolved", meeting_hash=hash_meeting_id(existing_meeting.id))
            # Return the database record for consistency
            return MeetingResponse(
                summary=existing_meeting.summary_text,
                action_items=existing_meeting.action_items or [],
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
        logger.warning("invalid_user_id_format_history")  # Don't log PII
        raise ValidationError("Invalid user_id format.") from e
    
    try:
        start_time = time.perf_counter()
        
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
        
        # Fetch all usage data in one query to avoid N+1 problem
        meeting_ids = [m.id for m in meetings]
        usage_map = {}
        
        if meeting_ids:
            usage_start = time.perf_counter()
            usage_result = await db.execute(
                select(
                    UsageRecord.meeting_id,
                    func.sum(UsageRecord.total_tokens).label('tokens'),
                    func.sum(UsageRecord.estimated_cost).label('cost')
                ).where(UsageRecord.meeting_id.in_(meeting_ids))
                .group_by(UsageRecord.meeting_id)
            )
            usage_map = {row.meeting_id: (row.tokens, row.cost) for row in usage_result}
            usage_duration = time.perf_counter() - usage_start
            logger.info("usage_batch_fetch_complete", duration_seconds=round(usage_duration, 3), meeting_count=len(meeting_ids))
        
        for meeting in meetings:
            # Lookup usage info from the pre-fetched map
            tokens, cost = usage_map.get(meeting.id, (0, 0))
            
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
        
        total_duration = time.perf_counter() - start_time
        logger.info("user_meetings_retrieved", user_hash=hash_user_id(user_uuid), count=len(meetings_data), duration_seconds=round(total_duration, 3))
        return meetings_data, total_count
    
    except ValidationError:
        # Re-raise validation errors as-is (don't convert to DatabaseError)
        raise
    except AIServiceError:
        # Re-raise AI service errors as-is
        raise
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
            logger.warning("meeting_not_found", user_hash=hash_user_id(user_uuid))
            raise NotFoundError("Meeting not found or access denied.")
        
        # Get aggregated usage info (sum across multiple usage records)
        # Use subquery to get most recent model name instead of max (which is lexicographic)
        most_recent_model = select(UsageRecord.model_name).where(
            UsageRecord.meeting_id == meeting.id
        ).order_by(UsageRecord.created_at.desc()).limit(1).scalar_subquery()
        
        usage_result = await db.execute(
            select(
                func.sum(UsageRecord.total_tokens).label('total_tokens'),
                func.sum(UsageRecord.estimated_cost).label('estimated_cost'),
                func.sum(UsageRecord.prompt_tokens).label('prompt_tokens'),
                func.sum(UsageRecord.completion_tokens).label('completion_tokens'),
                most_recent_model.label('model_name')
            ).where(UsageRecord.meeting_id == meeting.id)
        )
        usage_row = usage_result.one_or_none()
        
        return {
            "id": str(meeting.id),
            "created_at": meeting.created_at,
            "summary": meeting.summary_text,
            "action_items": meeting.action_items or [],
            "total_tokens": usage_row.total_tokens if usage_row and usage_row.total_tokens else 0,
            "estimated_cost": usage_row.estimated_cost if usage_row and usage_row.estimated_cost else 0,
            "model_name": usage_row.model_name if usage_row else None,
            "prompt_tokens": usage_row.prompt_tokens if usage_row and usage_row.prompt_tokens else 0,
            "completion_tokens": usage_row.completion_tokens if usage_row and usage_row.completion_tokens else 0
        }
    
    except NotFoundError:
        # Re-raise not found errors as-is (for 404 responses)
        raise
    except ValidationError:
        # Re-raise validation errors as-is (don't convert to DatabaseError)
        raise
    except AIServiceError:
        # Re-raise AI service errors as-is
        raise
    except Exception as e:
        logger.error("get_meeting_detail_failed", error=str(e))
        raise DatabaseError("Failed to retrieve meeting details.") from e
