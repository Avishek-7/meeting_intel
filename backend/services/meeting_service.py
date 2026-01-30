from core.exceptions import ValidationError, AIServiceError, DatabaseError
from ai_engine.pipeline import analyze_meeting
from schemas.meeting import MeetingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
from models.meeting import Meeting, ActionItem
from core.cache import redis_client
from core.cache_keys import meeting_cache_key
import json
import logging
import time

logger = logging.getLogger(__name__)

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
        db: AsyncSession
) -> MeetingResponse:
    """
    Handles meeting transcript processing.
    Business logic lives here, not in routes.
    """
    logger.info("Processing meeting transcript.")
    # Business rule validation
    if len(transcript) < 10:
        logger.warning("Transcript too short to process.")
        raise ValidationError("Transcript is too short to process.")

    cache_key = meeting_cache_key(transcript)

    cached_result = None
    try:
        cached_result = redis_client.get(cache_key)
    except Exception as e:
        logger.warning("Redis GET failed; proceeding without cache.", exc_info=e)

    from_cache = False
    if cached_result:
        logger.info(f"Cache HIT for key: {cache_key}")
        try:
            result = json.loads(cached_result)
        except (TypeError, ValueError) as e:
            logger.error("Failed to decode cached AI response.", exc_info=e)
            raise AIServiceError("Cached AI response is corrupted.") from e

        try:
            _validate_ai_result(result)
        except AIServiceError:
            logger.error("Cached AI response failed validation.")
            raise AIServiceError("Cached AI response is corrupted.")
        from_cache = True

    else:
        logger.info(f"Cache MISS for key: {cache_key} calling AI engine.")
        ai_start = time.perf_counter()
        result = await run_in_threadpool(analyze_meeting, transcript)
        ai_duration = time.perf_counter() - ai_start
        logger.info(f"AI processing complete in {ai_duration:.2f}s, caching result.")
        _validate_ai_result(result)

        try:
            redis_client.setex(
                cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(result)
            )
            logger.info(f"Cached AI response with TTL {CACHE_TTL_SECONDS}s.")
        except Exception as e:
            logger.warning("Redis SETEX failed; continuing without cache.", exc_info=e)
    
    logger.info("Checking for existing transcript in database.")
    existing = await db.execute(
        select(Meeting.id).where(Meeting.transcript == transcript)
    )
    existing_meeting_id = existing.scalar_one_or_none()
    if existing_meeting_id is not None:
        logger.info("Meeting already persisted; returning cached summary and action items.")
        return MeetingResponse(
            summary=result["summary"],
            action_items=result["action_items"],
        )

    try:
        logger.info("Persisting meeting data to database.")
        async with db.begin():
            meeting = Meeting(
                transcript=transcript,
                summary=result["summary"]
            )
            db.add(meeting)
            await db.flush()

            action_items = [
                ActionItem(meeting_id=meeting.id, content=item)
                for item in result["action_items"]
            ]
            db.add_all(action_items)
        logger.info("Meeting data persisted successfully.")
    except IntegrityError as e:
        logger.warning("Concurrent insert detected; rolling back and fetching existing entry.", exc_info=e)
        await db.rollback()
        existing = await db.execute(
            select(Meeting.id).where(Meeting.transcript == transcript)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("Concurrent insert resolved; returning result.")
            return MeetingResponse(
                summary=result["summary"],
                action_items=result["action_items"],
            )
        raise DatabaseError("Failed to persist meeting data.") from e
    except SQLAlchemyError as e:
        logger.error("Database error while persisting meeting data.", exc_info=e)
        raise DatabaseError("Failed to persist meeting data.") from e

    return MeetingResponse(
        summary=result["summary"],
        action_items=result["action_items"],
    )


