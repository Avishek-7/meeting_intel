"""
RQ job: transcribe uploaded audio and then trigger meeting analysis.
"""

import asyncio
import logging
from sqlalchemy import select
from core.database import get_async_session
from models.meeting import Meeting
from services.ai.transcription import transcribe_audio_file
from services.meeting_service import process_meeting_transcript

logger = logging.getLogger(__name__)


async def _run_transcription_job(meeting_id: str, user_id: str) -> dict:
    async with get_async_session() as db:
        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user_id)
        )
        meeting = result.scalar_one_or_none()
        if meeting is None:
            raise ValueError(f"Meeting {meeting_id} not found for user {user_id}")

        # Mark as processing
        meeting.transcription_status = "processing"
        await db.commit()

        try:
            transcript = await transcribe_audio_file(meeting.audio_file_path)
        except Exception as exc:
            meeting.transcription_status = "failed"
            await db.commit()
            raise

        # Persist transcript
        meeting.transcript_text = transcript
        meeting.transcription_status = "transcribed"
        await db.commit()

    # Now run analysis in a fresh session
    async with get_async_session() as db:
        analysis = await process_meeting_transcript(
            transcript=transcript, db=db, user_id=user_id
        )
        # Refresh meeting record to apply summary + action_items
        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = result.scalar_one_or_none()
        if meeting:
            meeting.transcription_status = "done"
            await db.commit()

    return {
        "meeting_id": meeting_id,
        "summary": analysis.summary,
        "action_items": [item.model_dump() for item in (analysis.action_items or [])],
    }


def run_transcription_job_sync(meeting_id: str, user_id: str) -> dict:
    """Synchronous wrapper for RQ worker."""
    logger.info("transcription_job_started", extra={"meeting_id": meeting_id})
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        raise RuntimeError(
            "run_transcription_job_sync cannot be called from an async context. "
            "Use _run_transcription_job directly."
        )
    result = asyncio.run(_run_transcription_job(meeting_id, user_id))
    logger.info("transcription_job_complete", extra={"meeting_id": meeting_id})
    return result
