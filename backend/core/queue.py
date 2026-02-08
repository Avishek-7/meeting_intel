from typing import Optional
from redis import Redis
from rq import Queue
from core.config import settings

redis_client: Optional[Redis]
default_queue: Optional[Queue]

if settings.redis_url:
    redis_client = Redis.from_url(
        settings.redis_url,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
    )
    default_queue = Queue(
        "default",
        connection=redis_client,
        default_timeout=300,  # 5 minutes
    )
else:
    redis_client = None
    default_queue = None

