from core.cache import get_redis_client
from core.cache_keys import meeting_cache_key
import logging

logger = logging.getLogger(__name__)

redis_client = get_redis_client()

def invalidate_meeting_cache(transcript: str) -> None:
    """Invalidate the cache for a given meeting transcript."""
    cache_key = meeting_cache_key(transcript)
    
    try:
        redis_client.delete(cache_key)
    except Exception as e:
        logger.error(f"Failed to invalidate cache for key: {cache_key}", exc_info=True)

