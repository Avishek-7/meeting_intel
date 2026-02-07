import redis
import os
from functools import lru_cache
from typing import Optional
import logging
from core.config import settings

REDIS_URL = settings.redis_url
REDIS_SOCKET_TIMEOUT = settings.redis_socket_timeout
REDIS_SOCKET_CONNECT_TIMEOUT = settings.redis_socket_connect_timeout

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_redis_client() -> Optional[redis.Redis]:
    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
        )
        client.ping()
        return client
    except Exception as e:
        logger.warning("redis_unavailable", extra={"error": str(e)})
        return None