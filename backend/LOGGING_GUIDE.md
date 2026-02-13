"""
Logging Best Practices Guide

This module demonstrates how to use the improved logging system in the application.
All logging should follow these patterns for consistency and better debugging.
"""

# ==============================================================================
# 1. BASIC STRUCTURED LOGGING
# ==============================================================================

from core.log_utils import log_info, log_warning, log_error, log_debug
import structlog

logger = structlog.get_logger(__name__)

# ✓ GOOD: Structured data with descriptive keys
log_info("user_authenticated", user_id="hash_123", method="password")

# ✓ GOOD: Include context for correlation
log_info("database_query", operation="fetch_user_by_email", rows_affected=1)

# ✗ BAD: Unstructured string-based logging
# logger.info("User authenticated")  # No structure, hard to filter/search


# ==============================================================================
# 2. ERROR LOGGING
# ==============================================================================

# ✓ GOOD: Use log_error helper with full exception context
try:
    result = await db.query(User).filter(User.id == user_id).first()
except Exception as e:
    log_error(
        event="user_lookup_failed",
        error=e,
        context={"user_id": "hash_123", "query": "fetch_user"},
        operation="get_user_by_id"
    )

# ✓ GOOD: Log errors with operation context
try:
    await cache.set(key, value)
except Exception as e:
    log_error(
        "cache_write_failed",
        e,
        context={"cache_key": "meeting_123", "ttl_seconds": 600}
    )


# ==============================================================================
# 3. OPERATION TRACKING WITH TIMING
# ==============================================================================

from core.log_utils import log_operation

# ✓ GOOD: Track operation duration and success/failure automatically
async def get_user_with_meetings(user_id: str):
    async with log_operation(
        "fetch_user_with_meetings",
        user_id="hash_123",
        include_meetings=True
    ) as monitor:
        user = await db.get_user(user_id)
        user.meetings = await db.get_user_meetings(user_id)
        monitor.result = user
        return user

# Output logs:
# event=fetch_user_with_meetings status=success duration_sec=0.1234 user_id=hash_123

# ✓ GOOD: Using with explicit context
async def process_transcript(transcript: str, user_id: str):
    async with log_operation(
        "transcript_processing",
        context={"user_id": "hash_456"},
        transcript_length=len(transcript),
        model="gpt-4o-mini"
    ) as monitor:
        result = await ai_engine.analyze(transcript)
        monitor.result = result  # Logs result summary
        return result


# ==============================================================================
# 4. FUNCTION CALL LOGGING (Decorator)
# ==============================================================================

from core.log_utils import log_function_call

# ✓ GOOD: Automatic timing and error tracking on functions
@log_function_call
async def fetch_analytics(user_id: str, days: int = 30) -> dict:
    """
    Function is automatically logged with:
    - function_executed event
    - duration_sec (execution time)
    - status (success/error)
    - Any raised exceptions are logged with full traceback
    """
    result = await db.get_user_analytics(user_id, days)
    return result


# ==============================================================================
# 5. LOG LEVELS - WHEN TO USE EACH
# ==============================================================================

# DEBUG: Detailed information for debugging (variable values, intermediate steps)
log_debug(
    "token_validation_step",
    token_exp=expire_time,
    current_time=now,
    is_valid=is_valid
)

# INFO: General informational messages about normal operation
log_info(
    "meeting_analysis_completed",
    meeting_id="m123",
    summary_length=500,
    action_items_count=3,
    duration_sec=2.5
)

# WARNING: Something unexpected happened, but app continues
log_warning(
    "cache_miss",
    cache_key="meeting_123",
    falling_back_to="database"
)
log_warning(
    "invalid_token_format",
    error="missing_exp_claim",
    fallback="token_validation_disabled"
)

# ERROR: Serious error that needs attention
log_error(
    "database_connection_failed",
    e,
    context={"pool_size": 5, "timeout": 10},
    operation="get_db_session"
)


# ==============================================================================
# 6. CONTEXT VARIABLES (Automatic Request Context)
# ==============================================================================

# These are automatically set in request middleware and included in ALL logs:
# - correlation_id: Unique ID for tracing request through system
# - request_id: HTTP request ID
# - method: HTTP method
# - path: URL path
# - query_params: Query parameters
# - user_hash: Anonymized user ID (never raw user_id!)

# Example: All logs from this request will include:
# correlation_id=abc123 method=POST path=/meetings/analyze

# When logging, you can add to context:
import structlog
structlog.contextvars.bind_contextvars(
    user_hash="u_hash_123",
    meeting_id="m_hash_456"
)


# ==============================================================================
# 7. REAL-WORLD EXAMPLES
# ==============================================================================

# Example 1: Database operation with error handling
async def update_user_role(user_id: str, new_role: str):
    async with log_operation(
        "update_user_role",
        user_id=user_id,
        new_role=new_role
    ) as monitor:
        try:
            user = await db.get_user(user_id)
            user.role = new_role
            await db.commit()
            log_info("user_role_updated", user_id=user_id, new_role=new_role)
            monitor.result = user
            return user
        except IntegrityError as e:
            log_warning(
                "role_update_conflict",
                user_id=user_id,
                new_role=new_role,
                reason="duplicate_role"
            )
            raise
        except Exception as e:
            log_error(
                "role_update_failed",
                e,
                context={"user_id": user_id, "new_role": new_role},
                operation="update_user_role"
            )
            raise


# Example 2: Cache operations with fallback
async def get_meeting_with_fallback(meeting_id: str):
    async with log_operation("fetch_meeting", meeting_id=meeting_id) as monitor:
        # Try cache first
        try:
            cached = await cache.get(f"meeting:{meeting_id}")
            if cached:
                log_info("cache_hit", cache_key=f"meeting:{meeting_id}")
                monitor.result = cached
                return cached
        except Exception as e:
            log_warning("cache_read_failed", cache_key=f"meeting:{meeting_id}", error=str(e))
        
        # Fall back to database
        log_debug("cache_miss", cache_key=f"meeting:{meeting_id}", fallback="database")
        meeting = await db.get_meeting(meeting_id)
        
        # Try to cache for next time
        try:
            await cache.set(f"meeting:{meeting_id}", meeting, ttl=600)
        except Exception as e:
            log_warning("cache_write_failed", error=str(e))
        
        monitor.result = meeting
        return meeting


# ==============================================================================
# 8. PRIVACY - NEVER LOG PII
# ==============================================================================

# ✗ BAD: Raw user IDs and emails
# logger.error(f"Error processing user {user_id} with email {email}")

# ✓ GOOD: Hash sensitive data
from core.privacy import hash_user_id, hash_meeting_id

log_error(
    "user_processing_failed",
    Exception("auth failed"),
    context={
        "user_id": hash_user_id(user_id),
        "operation": "create_meeting"
    }
)


# ==============================================================================
# 9. ADMIN/AUDIT LOGGING
# ==============================================================================

from core.rbac import log_admin_action, log_authorization_failure

# Track admin operations for compliance/audit
log_admin_action(
    username="admin_user",
    action="delete_user",
    resource="user_123",
    details={"reason": "account_closure", "backup_created": True},
    success=True
)

# Track authorization failures for security
log_authorization_failure(
    username="attacker",
    action="access_admin_panel",
    reason="insufficient_role:user"
)


# ==============================================================================
# 10. SEARCH/FILTER LOGS BY STRUCTURED FIELDS
# ==============================================================================

# With structured logging, you can easily search/filter:
# 
# Find all failed operations:
#   grep "status=failure" app.log
#
# Find slow operations (> 1 second):
#   grep "duration_sec=[1-9]\|duration_sec=[0-9][0-9]" app.log
#
# Find all errors in a specific request:
#   grep "correlation_id=abc123.*ERROR" app.log
#
# Find all user authentication issues:
#   grep "event=.*_auth" app.log
#
# Find operations by user:
#   grep "user_hash=u_123" app.log
