from services.ai.client import call_ai
from core.exceptions import ValidationError, AIServiceError

def process_meeting_transcript(transcript: str) -> dict:
    """
    Handles meeting transcript processing.
    Business logic lives here, not in routes.
    """
    # Business rule validation
    if len(transcript) < 10:
        raise ValidationError("Transcript is too short to process.")

    result = call_ai(transcript)

    # Validate AI response shape before returning
    if not isinstance(result, dict):
        raise AIServiceError("AI service returned invalid response.")
    if "summary" not in result or "action_items" not in result:
        raise AIServiceError("AI response missing required fields.")

    return result


