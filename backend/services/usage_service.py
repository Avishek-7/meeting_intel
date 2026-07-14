from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, func, and_
from models.usage_record import UsageRecord
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from core.privacy import hash_user_id, hash_meeting_id
from core.config import settings
from core.exceptions import ValidationError
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


def _get_today_range_utc() -> tuple[datetime, datetime]:
    """Get today's date range in UTC with timezone-aware datetimes."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


async def get_user_daily_usage_totals(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[int, Decimal]:
    start, end = _get_today_range_utc()
    result = await db.execute(
        select(
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
        ).where(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.created_at >= start,
                UsageRecord.created_at < end,
            )
        )
    )
    row = result.one()
    total_tokens = int(row[0] or 0)
    total_cost = row[1] or Decimal("0.00")
    return total_tokens, total_cost


async def enforce_daily_usage_limits(
    db: AsyncSession,
    user_id: uuid.UUID,
    estimated_tokens: int = 0,
) -> None:
    if settings.DAILY_TOKEN_CAP is None and settings.DAILY_COST_CAP_USD is None:
        return

    total_tokens, total_cost = await get_user_daily_usage_totals(db, user_id)

    if settings.DAILY_TOKEN_CAP is not None:
        projected_tokens = total_tokens + max(estimated_tokens, 0)
        if projected_tokens > settings.DAILY_TOKEN_CAP:
            raise ValidationError("Daily token cap exceeded.")

    if settings.DAILY_COST_CAP_USD is not None:
        estimated_cost = Decimal("0.00")
        if estimated_tokens > 0:
            estimated_cost = calculate_cost(
                settings.OPENAI_MODEL,
                max(estimated_tokens, 0),
                settings.OPENAI_MAX_TOKENS_PER_REQUEST,
            )
        projected_cost = total_cost + estimated_cost
        if projected_cost > settings.DAILY_COST_CAP_USD:
            raise ValidationError("Daily cost cap exceeded.")

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
        logger.error("usage_track_failed", error_type=type(e).__name__, exc_info=True)
        await db.rollback()
        raise
