import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_async_session
from core.retry import retry_async
import structlog
from services.meeting_service import process_meeting_transcript
from models.meeting import Meeting
from core.transcript import generate_transcript_hash
from core.privacy import hash_meeting_id

logger = structlog.get_logger("jobs.meeting_analysis")

async def run_meeting_analysis_job(transcript: str, user_id: str, db: AsyncSession):
    """
    Analyzes a meeting transcript and persists results.
    
    Race condition is handled in process_meeting_transcript via IntegrityError 
    catching and duplicate lookups. No need for redundant checks here.
    """
    logger.info("meeting_analysis_job_started", transcript_length=len(transcript))
    
    # Let process_meeting_transcript handle duplicate detection and race conditions
    response = await process_meeting_transcript(transcript=transcript, db=db, user_id=user_id)
    
    # Query for the meeting_id after processing with user_id filter for proper isolation
    transcript_hash = generate_transcript_hash(transcript)
    result = await db.execute(
        select(Meeting.id).where(
            Meeting.transcript_hash == transcript_hash,
            Meeting.user_id == user_id
        )
    )
    meeting_id = result.scalar_one_or_none()

    logger.info(
        "meeting_analysis_job_complete",
        action_count=len(response.action_items) if response.action_items else 0,
        meeting_hash=hash_meeting_id(meeting_id) if meeting_id else None,
    )
    
    return {
        "meeting_id": str(meeting_id) if meeting_id else None,
        "summary": response.summary,
        "action_items": [item.model_dump() for item in response.action_items] if response.action_items else [],
    }

def run_meeting_analysis_job_sync(transcript: str, user_id: str):
    async def _run():
        async def _attempt():
            async with get_async_session() as db:
                return await run_meeting_analysis_job(
                    transcript=transcript,
                    user_id=user_id,
                    db=db,
                )
        return await retry_async(_attempt)
    logger.info("meeting_analysis_job_sync_started")
    result = asyncio.run(_run())
    logger.info("meeting_analysis_job_sync_completed")
    return result