"""
Role-Based Access Control (RBAC) system.

Provides:
- Role and Permission enums for type safety
- Hierarchical role permissions
- Reusable dependency functions for route protection
- Audit logging utilities
"""

from enum import Enum
from typing import Set, Optional, FrozenSet
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """Application roles with hierarchy."""
    ADMIN = "admin"
    USER = "user"


class Permission(str, Enum):
    """Fine-grained permissions for authorization."""
    # Meeting operations
    CREATE_MEETING = "create:meeting"
    READ_OWN_MEETING = "read:own_meeting"
    READ_ALL_MEETINGS = "read:all_meetings"
    DELETE_OWN_MEETING = "delete:own_meeting"
    DELETE_ALL_MEETINGS = "delete:all_meetings"
    
    # Analytics
    READ_OWN_ANALYTICS = "read:own_analytics"
    READ_GLOBAL_ANALYTICS = "read:global_analytics"
    
    # User management
    MANAGE_USERS = "manage:users"
    
    # Audit
    READ_AUDIT_LOG = "read:audit_log"


# Map roles to their permissions
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.CREATE_MEETING,
        Permission.READ_OWN_MEETING,
        Permission.READ_ALL_MEETINGS,
        Permission.DELETE_OWN_MEETING,
        Permission.DELETE_ALL_MEETINGS,
        Permission.READ_OWN_ANALYTICS,
        Permission.READ_GLOBAL_ANALYTICS,
        Permission.MANAGE_USERS,
        Permission.READ_AUDIT_LOG,
    },
    Role.USER: {
        Permission.CREATE_MEETING,
        Permission.READ_OWN_MEETING,
        Permission.DELETE_OWN_MEETING,
        Permission.READ_OWN_ANALYTICS,
    },
}


@lru_cache(maxsize=128)
def get_role_permissions(role: Role) -> FrozenSet[Permission]:
    """Get all permissions for a given role."""
    return frozenset(ROLE_PERMISSIONS.get(role, set()))


def has_permission(user_context: dict, permission: Permission) -> bool:
    """Check if user has a specific permission."""
    role_str = user_context.get("role", Role.USER.value)
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.USER
    
    permissions = get_role_permissions(role)
    return permission in permissions


def log_admin_action(
    username: str,
    action: str,
    resource: str,
    details: Optional[dict] = None,
    success: bool = True,
) -> None:
    """
    Log administrative actions for audit trail.
    
    IMPORTANT: username should be anonymized before passing (e.g., via hash_user_id()).
    Logging raw usernames violates GDPR/CCPA data protection requirements.
    
    Args:
        username: User identifier (should be hashed for PII protection)
        action: Admin action performed (e.g., "delete_user", "modify_role")
        resource: What was affected (user ID, resource name, etc.)
        details: Additional context as dict
        success: Whether the action succeeded
    """
    status = "SUCCESS" if success else "FAILURE"
    detail_str = f" | {details}" if details else ""
    logger.warning(
        f"ADMIN_ACTION [{status}] | user={username} | action={action} | resource={resource}{detail_str}"
    )


def log_authorization_failure(
    username: str,
    action: str,
    reason: str,
) -> None:
    """
    Log authorization failures for security monitoring.
    
    IMPORTANT: username should be anonymized before passing (e.g., via hash_user_id()).
    Logging raw usernames violates GDPR/CCPA data protection requirements.
    
    Args:
        username: User identifier (should be hashed for PII protection)
        action: Action that was attempted
        reason: Why authorization failed
    """
    logger.warning(
        f"AUTHORIZATION_FAILURE | user={username} | action={action} | reason={reason}"
    )
