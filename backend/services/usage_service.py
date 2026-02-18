from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from models.usage_record import UsageRecord
from decimal import Decimal
from core.privacy import hash_user_id, hash_meeting_id
import uuid
import structlog

logger = structlog.get_logger("services.usage_service")

# Token pricing per 1M tokens (example rates - adjust based on your model)
MODEL_PRICING = {
    "gpt-4": {
        "prompt": Decimal("30.00"),  # $30 per 1M prompt tokens
        "completion": Decimal("60.00")  # $60 per 1M completion tokens
    },
    "gpt-4o-mini": {
        "prompt": Decimal("0.150"),  # $0.15 per 1M prompt tokens
        "completion": Decimal("0.600")  # $0.60 per 1M completion tokens
    },
    "gpt-3.5-turbo": {
        "prompt": Decimal("0.50"),  # $0.50 per 1M prompt tokens
        "completion": Decimal("1.50")  # $1.50 per 1M completion tokens
    },
    "claude-3-sonnet": {
        "prompt": Decimal("3.00"),
        "completion": Decimal("15.00")
    }
}

def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Calculate estimated cost based on model and token usage."""
    # Validate token counts
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("Token counts cannot be negative")
    
    # Get pricing and warn if model is unknown
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["gpt-3.5-turbo"])
    if model_name not in MODEL_PRICING:
        logger.warning(f"Unknown model '{model_name}', using default pricing (gpt-3.5-turbo)")
    
    prompt_cost = (Decimal(prompt_tokens) / Decimal("1000000")) * pricing["prompt"]
    completion_cost = (Decimal(completion_tokens) / Decimal("1000000")) * pricing["completion"]
    
    return prompt_cost + completion_cost

async def track_ai_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    meeting_id: uuid.UUID,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int
) -> UsageRecord:
    """
    Track AI usage for a meeting.
    
    Args:
        db: Database session
        user_id: UUID of the user
        meeting_id: UUID of the meeting
        model_name: Name of the AI model used
        prompt_tokens: Number of prompt tokens used
        completion_tokens: Number of completion tokens used
    
    Returns:
        Created UsageRecord
    """
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost = calculate_cost(model_name, prompt_tokens, completion_tokens)
    
    try:
        usage_record = UsageRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            meeting_id=meeting_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost
        )
        
        db.add(usage_record)
        await db.commit()
        await db.refresh(usage_record)
        
        # Log with hashed identifiers for privacy compliance (GDPR/CCPA)
        # Avoid logging raw identifiers that could be linked to individuals
        logger.info(
            "usage_tracked",
            user_hash=hash_user_id(user_id),
            meeting_hash=hash_meeting_id(meeting_id),
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=str(estimated_cost),
        )
        
        return usage_record
        
    except SQLAlchemyError as e:
        logger.error("usage_track_failed", error_type=type(e).__name__, exc_info=False)
        await db.rollback()
        raise
