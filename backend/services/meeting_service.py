from core.exceptions import ValidationError, AIServiceError, DatabaseError
from ai_engine.pipeline import analyze_meeting
from schemas.meeting import MeetingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
from models.meeting import Meeting
from core.cache import get_redis_client
from core.cache_keys import meeting_cache_key
from core.cache_invalidation import invalidate_meeting_cache
from services.usage_service import track_ai_usage
import json
import structlog
import time
from jobs.meeting_analysis import generate_transcript_hash
import uuid

logger = structlog.get_logger("services.meeting_service")
redis_client = get_redis_client()

CACHE_TTL_SECONDS = 60 * 10 # 10 minutes

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


