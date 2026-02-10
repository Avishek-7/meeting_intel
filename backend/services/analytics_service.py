from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast
from sqlalchemy.types import Date
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
from models.usage_record import UsageRecord
from models.meeting import Meeting
from models.user import User
import structlog

logger = structlog.get_logger("services.analytics_service")


async def get_user_stats(
    db: AsyncSession,
    user_id: str,
    date_from: datetime,
    date_to: datetime
) -> Dict:
    """
    Get aggregated stats for a user within a date range.
    
    Returns:
        Dict with total_cost, total_tokens, total_meetings, cost_by_model
    """
    try:
        # Query: sum of cost and tokens, grouped by model
        result = await db.execute(
            select(
                func.sum(UsageRecord.estimated_cost).label("total_cost"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                UsageRecord.model_name
            ).where(
                and_(
                    UsageRecord.user_id == user_id,
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            ).group_by(UsageRecord.model_name)
        )
        
        rows = result.fetchall()
        
        total_cost = Decimal("0.00")
        total_tokens = 0
        cost_by_model = {}
        
        for row in rows:
            row_cost = row[0] or Decimal("0.00")
            row_tokens = row[1] or 0
            model_name = row[2]
            
            total_cost += row_cost
            total_tokens += row_tokens
            cost_by_model[model_name] = row_cost
        
        # Separate query for distinct meeting count (not grouped by model)
        meeting_count_result = await db.execute(
            select(func.count(UsageRecord.meeting_id.distinct())).where(
                and_(
                    UsageRecord.user_id == user_id,
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            )
        )
        total_meetings = meeting_count_result.scalar() or 0
        
        logger.info(
            "user_stats_retrieved",
            user_id=str(user_id)[:8],
            total_cost=str(total_cost),
            total_tokens=total_tokens,
            total_meetings=total_meetings
        )
        
        return {
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_meetings": total_meetings,
            "cost_by_model": cost_by_model,
            "period_start": date_from,
            "period_end": date_to
        }
    except Exception as e:
        logger.error("user_stats_failed", error=str(e))
        raise


async def get_user_daily_stats(
    db: AsyncSession,
    user_id: str,
    date_from: datetime,
    date_to: datetime
) -> List[Dict]:
    """
    Get daily breakdown of user stats.
    
    Returns:
        List of dicts: [{date, cost, token_count, meeting_count}, ...]
    """
    try:
        result = await db.execute(
            select(
                cast(UsageRecord.created_at, Date).label("date"),
                func.sum(UsageRecord.estimated_cost).label("cost"),
                func.sum(UsageRecord.total_tokens).label("token_count"),
                func.count(UsageRecord.meeting_id.distinct()).label("meeting_count")
            ).where(
                and_(
                    UsageRecord.user_id == user_id,
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            ).group_by(cast(UsageRecord.created_at, Date))
            .order_by(cast(UsageRecord.created_at, Date))
        )
        
        rows = result.fetchall()
        daily_stats = []
        
        for row in rows:
            daily_stats.append({
                "date": str(row[0]),
                "cost": row[1] or Decimal("0.00"),
                "token_count": row[2] or 0,
                "meeting_count": row[3] or 0
            })
        
        logger.info("user_daily_stats_retrieved", days_count=len(daily_stats))
        return daily_stats
    except Exception as e:
        logger.error("user_daily_stats_failed", error=str(e))
        raise


async def get_global_stats(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime
) -> Dict:
    """
    Get global stats across all users.
    
    Returns:
        Dict with total_cost, total_users, total_meetings, total_tokens, cost_by_model
    """
    try:
        # Total cost and tokens
        usage_result = await db.execute(
            select(
                func.sum(UsageRecord.estimated_cost).label("total_cost"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                UsageRecord.model_name
            ).where(
                and_(
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            ).group_by(UsageRecord.model_name)
        )
        
        usage_rows = usage_result.fetchall()
        total_cost = Decimal("0.00")
        total_tokens = 0
        cost_by_model = {}
        
        for row in usage_rows:
            row_cost = row[0] or Decimal("0.00")
            row_tokens = row[1] or 0
            model_name = row[2]
            
            total_cost += row_cost
            total_tokens += row_tokens
            cost_by_model[model_name] = row_cost
        
        # Separate query for distinct meeting count (not grouped by model)
        meeting_count_result = await db.execute(
            select(func.count(UsageRecord.meeting_id.distinct())).where(
                and_(
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            )
        )
        total_meetings = meeting_count_result.scalar() or 0
        
        # Count distinct users
        user_result = await db.execute(
            select(func.count(UsageRecord.user_id.distinct())).where(
                and_(
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            )
        )
        total_users = user_result.scalar() or 0
        
        logger.info(
            "global_stats_retrieved",
            total_cost=str(total_cost),
            total_tokens=total_tokens,
            total_meetings=total_meetings,
            total_users=total_users
        )
        
        return {
            "total_cost": total_cost,
            "total_users": total_users,
            "total_meetings": total_meetings,
            "total_tokens": total_tokens,
            "cost_by_model": cost_by_model,
            "period_start": date_from,
            "period_end": date_to
        }
    except Exception as e:
        logger.error("global_stats_failed", error=str(e))
        raise


async def get_global_daily_stats(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime
) -> List[Dict]:
    """
    Get global daily breakdown.
    
    Returns:
        List of dicts: [{date, cost, token_count, meeting_count}, ...]
    """
    try:
        result = await db.execute(
            select(
                cast(UsageRecord.created_at, Date).label("date"),
                func.sum(UsageRecord.estimated_cost).label("cost"),
                func.sum(UsageRecord.total_tokens).label("token_count"),
                func.count(UsageRecord.meeting_id.distinct()).label("meeting_count")
            ).where(
                and_(
                    UsageRecord.created_at >= date_from,
                    UsageRecord.created_at <= date_to
                )
            ).group_by(cast(UsageRecord.created_at, Date))
            .order_by(cast(UsageRecord.created_at, Date))
        )
        
        rows = result.fetchall()
        daily_stats = []
        
        for row in rows:
            daily_stats.append({
                "date": str(row[0]),
                "cost": row[1] or Decimal("0.00"),
                "token_count": row[2] or 0,
                "meeting_count": row[3] or 0
            })
        
        logger.info("global_daily_stats_retrieved", days_count=len(daily_stats))
        return daily_stats
    except Exception as e:
        logger.error("global_daily_stats_failed", error=str(e))
        raise


async def get_user_top_expensive_meetings(
    db: AsyncSession,
    user_id: str,
    limit: int = 10
) -> List[Dict]:
    """
    Get user's most expensive meetings (by cost).
    
    Returns:
        List of dicts: [{meeting_id, cost, tokens, created_at}, ...]
    """
    try:
        result = await db.execute(
            select(
                UsageRecord.meeting_id,
                func.sum(UsageRecord.estimated_cost).label("total_cost"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                func.max(UsageRecord.created_at).label("created_at")
            ).where(UsageRecord.user_id == user_id)
            .group_by(UsageRecord.meeting_id)
            .order_by(func.sum(UsageRecord.estimated_cost).desc())
            .limit(limit)
        )
        
        rows = result.fetchall()
        meetings = []
        
        for row in rows:
            meetings.append({
                "meeting_id": str(row[0]),
                "cost": row[1] or Decimal("0.00"),
                "tokens": row[2] or 0,
                "created_at": row[3]
            })
        
        logger.info("top_expensive_meetings_retrieved", count=len(meetings))
        return meetings
    except Exception as e:
        logger.error("top_expensive_meetings_failed", error=str(e))
        raise
        raise


def parse_date_range(from_param: str = None, to_param: str = None, preset: str = None) -> Tuple[datetime, datetime]:
    """
    Parse date range from params or preset.
    
    Args:
        from_param: ISO format date string (YYYY-MM-DD)
        to_param: ISO format date string (YYYY-MM-DD)
        preset: 'today', '7d', '30d', 'all'
    
    Returns:
        (date_from, date_to) tuple
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    # If custom range provided, use it
    if from_param and to_param:
        try:
            date_from = datetime.fromisoformat(from_param)
            date_to = datetime.fromisoformat(to_param)
            return date_from, date_to
        except ValueError:
            logger.warning("invalid_data_format", from_param=from_param, to_param=to_param)
    
        # Use preset
    if preset == "today":
        return today, tomorrow
    elif preset == "7d":
        return today - timedelta(days=7), tomorrow
    elif preset == "30d":
        return today - timedelta(days=30), tomorrow
    elif preset == "all":
        return datetime(2020, 1, 1), tomorrow
    
    # Default to today
    return today, tomorrow
