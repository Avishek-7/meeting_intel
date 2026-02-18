import logging
from typing import Optional
from redis import Redis
from rq import Queue
from core.config import settings
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def sanitize_redis_url(url: str) -> str:
    """Sanitize Redis URL by masking password to prevent credential leakage in logs."""
    try:
        parsed = urlparse(url)
        if parsed.password and parsed.hostname:
            # Replace password with asterisks
            netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            sanitized = parsed._replace(netloc=netloc)
            return urlunparse(sanitized)
        elif parsed.password:
            # Password exists but hostname is missing/invalid
            return "redis://***:***@<host>:<port>"
        return url
        
    except Exception:
        # If sanitization fails, return a generic placeholder
        return "redis://***:***@<host>:<port>"


redis_client: Optional[Redis]
default_queue: Optional[Queue]

if settings.redis_url:
    try:
        redis_client = Redis.from_url(
            settings.redis_url,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
        )
        redis_client.ping()
        default_queue = Queue(
            "default",
            connection=redis_client,
            default_timeout=300,  # 5 minutes
        )
    except Exception as e:
        sanitized_url = sanitize_redis_url(settings.redis_url)
        logger.error(
            "redis_connection_failed: %s, url=%s",
            type(e).__name__,
            sanitized_url
        )
        redis_client = None
        default_queue = None
else:
    redis_client = None
    default_queue = None

