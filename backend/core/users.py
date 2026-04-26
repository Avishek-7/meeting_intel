"""Fake User Store

WARNING: This is a placeholder for a real identity provider (OAuth2/OIDC, SSO, or
a proper user-management database). Replace this before handling real user data.

Passwords are loaded from environment variables so that no credentials are
hard-coded in source control. Set ADMIN_PASSWORD and USER_PASSWORD in your .env.
"""

import os
import logging
from core.security import hash_password
from core.rbac import Role

logger = logging.getLogger(__name__)

_admin_password = os.environ.get("ADMIN_PASSWORD", "")
_user_password = os.environ.get("USER_PASSWORD", "")

if not _admin_password or not _user_password:
    logger.warning(
        "ADMIN_PASSWORD or USER_PASSWORD env vars are not set. "
        "Set them in .env before running in production. "
        "Authentication will fail for built-in accounts."
    )

fake_users_db = {
    "avishek": {
        "username": "avishek",
        "hashed_password": hash_password(_user_password) if _user_password else "",
        "role": Role.USER.value,
    },
    "admin": {
        "username": "admin",
        "hashed_password": hash_password(_admin_password) if _admin_password else "",
        "role": Role.ADMIN.value,
    },
}
