from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from models.usage_record import UsageRecord
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

# Token pricing per 1M tokens (example rates - adjust based on your model)
MODEL_PRICING = {
    "gpt-4": {
        "prompt": Decimal("30.00"),  # $30 per 1M prompt tokens
        "completion": Decimal("60.00")  # $60 per 1M completion tokens
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
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["gpt-3.5-turbo"])
    
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
        
        logger.info(
            f"Tracked AI usage: user={user_id}, meeting={meeting_id}, "
            f"model={model_name}, tokens={total_tokens}, cost=${estimated_cost:.6f}"
        )
        
        return usage_record
        
    except SQLAlchemyError as e:
        logger.error("Failed to track AI usage", exc_info=e)
        await db.rollback()
        raise
