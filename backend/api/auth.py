import logging

from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from core.security import create_access_token
from core.config import settings
from core.database import get_db
from core.dependencies import get_current_user
from core.exceptions import ConflictError, DatabaseError
from schemas.auth import RegisterRequest, TokenResponse, UserResponse
from services.user_service import register_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    try:
        user = await register_user(
            db=db,
            email=body.email,
            password=body.password.get_secret_value(),
            display_name=body.display_name,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except DatabaseError:
        logger.exception("Database error during registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    token = create_access_token({"sub": str(user.id)})
    _set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan=user.plan,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login with email + password (form field `username` carries the email)."""
    try:
        user = await authenticate_user(db, email=form_data.username, password=form_data.password)
    except DatabaseError:
        logger.exception("Database error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(user.id)})
    _set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan=user.plan,
        ),
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserResponse(
        id=current_user["id"],
        email=current_user.get("email", ""),
        display_name=current_user.get("display_name"),
        role=current_user.get("role", "user"),
        plan=current_user.get("plan", "free"),
    )