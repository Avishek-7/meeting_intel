"""
Authorization dependencies for FastAPI routes.

Provides reusable dependency functions for role and permission-based access control.
"""

from typing import Callable
from fastapi import Depends, HTTPException, status
from core.dependencies import get_current_user
from core.rbac import Role, Permission, has_permission, log_authorization_failure
from core.privacy import hash_user_id


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to require admin role.
    
    Usage:
        @router.get("/admin-endpoint")
        async def admin_endpoint(current_user: dict = Depends(get_admin_user)):
            ...
    """
    username = current_user.get("username", "unknown")
    role_str = current_user.get("role", "user")
    
    if role_str != Role.ADMIN.value:
        # Hash username before logging (PII protection)
        username_hash = hash_user_id(username)
        log_authorization_failure(username_hash, "access_admin_resource", f"insufficient_role:{role_str}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return current_user


def require_permission(
    permission: Permission,
) -> Callable[..., dict]:
    """
    Factory for creating permission-based dependencies.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(
            current_user: dict = Depends(require_permission(Permission.MANAGE_USERS))
        ):
            ...
    """
    async def check_permission(current_user: dict = Depends(get_current_user)) -> dict:
        username = current_user.get("username", "unknown")
        
        if not has_permission(current_user, permission):
            # Hash username before logging (PII protection)
            username_hash = hash_user_id(username)
            log_authorization_failure(username_hash, permission.value, "insufficient_permissions")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required",
            )
        
        return current_user
    
    return check_permission
