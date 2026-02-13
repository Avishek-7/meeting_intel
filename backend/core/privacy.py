"""
Privacy utilities for handling PII in logs and external systems.

GDPR/CCPA Compliance:
- Never log raw user_id, email, or other PII
- Use anonymized hashes for correlation
- Implement log retention policies
"""

import hashlib
from typing import Union
import uuid
import logging
from core.config import settings

_logger = logging.getLogger(__name__)

_HASH_PEPPER = settings.PII_HASH_PEPPER

if not _HASH_PEPPER:
    _logger.warning(
        "PII_HASH_PEPPER is not set. Hashed identifiers are vulnerable to enumeration attacks. "
        "Set this environment variable in production."
    )


def hash_user_id(user_id: Union[str, uuid.UUID]) -> str:
    """
    Create anonymized hash of user_id for logging/correlation.
    
    This hash:
    - Cannot be reversed to get the original user_id
    - Is consistent for the same user (for log correlation)
    - Is short (12 chars) to reduce log verbosity while minimizing collision risk
    - Uses application secret (pepper) to prevent enumeration attacks
    
    Note: 12 hex chars = 48 bits, giving ~50% collision probability at ~16M users.
    Set PII_HASH_PEPPER environment variable in production.
    
    Args:
        user_id: User UUID (string or UUID object)
    
    Returns:
        12-character hash string for logging
    
    Example:
        >>> hash_user_id("123e4567-e89b-12d3-a456-426614174000")
        'a1b2c3d4e5f6'
    """
    user_id_str = str(user_id)
    return hashlib.sha256((_HASH_PEPPER + user_id_str).encode()).hexdigest()[:12]


def hash_meeting_id(meeting_id: Union[str, uuid.UUID]) -> str:
    """
    Create anonymized hash of meeting_id for logging.
    
    While meeting IDs are less sensitive than user IDs,
    consistent hashing allows for correlation without exposing full UUIDs.
    Uses application secret (pepper) to prevent enumeration attacks.
    
    Args:
        meeting_id: Meeting UUID (string or UUID object)
    
    Returns:
        12-character hash string for logging
    """
    meeting_id_str = str(meeting_id)
    return hashlib.sha256((_HASH_PEPPER + meeting_id_str).encode()).hexdigest()[:12]
