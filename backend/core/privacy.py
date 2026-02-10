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


def hash_user_id(user_id: Union[str, uuid.UUID]) -> str:
    """
    Create anonymized hash of user_id for logging/correlation.
    
    This hash:
    - Cannot be reversed to get the original user_id
    - Is consistent for the same user (for log correlation)
    - Is short (8 chars) to reduce log verbosity
    
    Args:
        user_id: User UUID (string or UUID object)
    
    Returns:
        8-character hash string for logging
    
    Example:
        >>> hash_user_id("123e4567-e89b-12d3-a456-426614174000")
        'a1b2c3d4'
    """
    user_id_str = str(user_id)
    return hashlib.sha256(user_id_str.encode()).hexdigest()[:8]


def hash_meeting_id(meeting_id: Union[str, uuid.UUID]) -> str:
    """
    Create anonymized hash of meeting_id for logging.
    
    While meeting IDs are less sensitive than user IDs,
    consistent hashing allows for correlation without exposing full UUIDs.
    
    Args:
        meeting_id: Meeting UUID (string or UUID object)
    
    Returns:
        8-character hash string for logging
    """
    meeting_id_str = str(meeting_id)
    return hashlib.sha256(meeting_id_str.encode()).hexdigest()[:8]
