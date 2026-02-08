import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_async_session
from core.retry import retry_async
import structlog
from services.meeting_service import process_meeting_transcript
from models.meeting import Meeting
from core.transcript import generate_transcript_hash

logger = structlog.get_logger("jobs.meeting_analysis")

async def run_meeting_analysis_job(transcript: str, user_id: str, db: AsyncSession):
    logger.info("meeting_analysis_job_started", transcript_length=len(transcript))
    transcript_hash = generate_transcript_hash(transcript)
    existing = await db.execute(
        select(Meeting).where(Meeting.transcript_hash == transcript_hash)
    )
    existing_meeting = existing.scalar_one_or_none()

    if existing_meeting is not None:
        logger.info(
            "meeting_analysis_job_skipped_duplicate",
            meeting_id=str(existing_meeting.id),
        )
        return {
            "meeting_id": str(existing_meeting.id),
            "summary": existing_meeting.summary_text,
            "action_items": existing_meeting.action_items,
        }

    response = await process_meeting_transcript(transcript=transcript, db=db, user_id=user_id)
    created = await db.execute(
        select(Meeting.id).where(Meeting.transcript_hash == transcript_hash)
    )
    meeting_id = created.scalar_one_or_none()

    logger.info(
        "meeting_analysis_job_complete",
        action_count=len(response.action_items),
        meeting_id=str(meeting_id) if meeting_id else None,
    )
    return {
        "meeting_id": str(meeting_id) if meeting_id else None,
        "summary": response.summary,
        "action_items": [item.model_dump() for item in response.action_items],
    }

def run_meeting_analysis_job_sync(transcript: str, user_id: str):
    async def _run():
        async with get_async_session() as db:
            return await retry_async(
                lambda: run_meeting_analysis_job(
                    transcript=transcript,
                    user_id=user_id,
                    db=db,
                )
            )
    logger.info("meeting_analysis_job_sync_started")
    result = asyncio.run(_run())
    logger.info("meeting_analysis_job_sync_completed")
    return result