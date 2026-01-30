import redis
import os
from functools import lru_cache

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0"))

@lru_cache(maxsize=1)
def get_redis_client():
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
    )