import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.exceptions import DatabaseError
from core.security import verify_access_token
from core.config import settings
from core.users import fake_users_db
from core.rbac import Role
from services.user_service import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

logger = logging.getLogger(__name__)

async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        token = request.cookies.get(settings.AUTH_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    username: str = payload.get("sub")
    user = fake_users_db.get(username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    user_context = dict(user)
    user_context["username"] = username
    if not user_context.get("email"):
        user_context["email"] = f"{username}@meetingintel.local"

    try:
        db_user = await get_user_by_email(db, user_context["email"])
    except DatabaseError:
        logger.warning("Database lookup failed for current user.")
        db_user = None

    if db_user is not None:
        if db_user.email:
            user_context["email"] = db_user.email
        if getattr(db_user, "role", None):
            user_context["role"] = db_user.role

    return user_context


