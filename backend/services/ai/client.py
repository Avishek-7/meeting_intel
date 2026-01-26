from core.exceptions import ValidationError, AIServiceError


def call_ai(prompt: str) -> dict:
    """
    Simulates AI call.
    Real AI integration will replace this later.
    """
    # Input validation (defensive)
    if not prompt or not prompt.strip():
        raise ValidationError("Transcript cannot be empty.")

    try:
        # Simulated AI call (real call later)
        return {
            "summary": "Simulated AI-generated meeting summary.",
            "action_items": []
        }
    except Exception as e:
        raise AIServiceError("AI service failed.") from e