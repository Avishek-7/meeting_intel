from core.exceptions import ValidationError, AIServiceError
from ai_engine.pipeline import analyze_meeting
from schemas.meeting import MeetingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from core.exceptions import DatabaseError
from models.meeting import Meeting, ActionItem

async def process_meeting_transcript(
        transcript: str,
        db: AsyncSession
) -> MeetingResponse:
    """
    Handles meeting transcript processing.
    Business logic lives here, not in routes.
    """
    # Business rule validation
    if len(transcript) < 10:
        raise ValidationError("Transcript is too short to process.")

    result = await run_in_threadpool(analyze_meeting, transcript)

    # Validate AI response shape before returning
    if not isinstance(result, dict):
        raise AIServiceError("AI service returned invalid response.")
    
    if "summary" not in result or "action_items" not in result:
        raise AIServiceError("AI response missing required fields.")
    
    try:
        async with db.begin():
            meeting = Meeting(
                transcript=transcript,
                summary=result["summary"]
            )
            db.add(meeting)
            await db.flush()

            for item in result["action_items"]:
                db.add(ActionItem(
                    meeting_id=meeting.id,
                    content=item
                ))
    except SQLAlchemyError as e:
        raise DatabaseError("Failed to persist meeting data.") from e

    return MeetingResponse(
        summary=result["summary"],
        action_items=result["action_items"],
    )


