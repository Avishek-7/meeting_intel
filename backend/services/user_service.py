from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
from models.user import User
from core.exceptions import DatabaseError, ConflictError
from core.security import hash_password, verify_password
from core.users import fake_users_db
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_email(email: Optional[str]) -> str:
    """Normalize email by stripping whitespace and converting to lowercase.
    
    Args:
        email: Email address to normalize, or None
        
    Returns:
        Normalized email string, or empty string if email is None
    """
    if email is None:
        return ""
    return email.strip().lower()

async def get_or_create_user_by_email(db: AsyncSession, email: str) -> User:
    """
    Get existing user by email or create a new one.
    
    Args:
        db: Database session
        email: User email address
    
    Returns:
        User object
    """
    try:
        # Normalize email for consistent querying and storage
        normalized_email = normalize_email(email)
        
        # Try to find existing user
        result = await db.execute(
            select(User).where(User.email == normalized_email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            logger.info("Found existing user")
            return user
        
        # Create new user with normalized email
        user = User(
            id=uuid.uuid4(),
            email=normalized_email
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info("Created new user")
        return user
        
    except IntegrityError:
        # Handle race condition - another request created the user
        await db.rollback()
        try:
            normalized_email = normalize_email(email)
            result = await db.execute(
                select(User).where(User.email == normalized_email)
            )
            user = result.scalar_one_or_none()
            if user:
                logger.info("User created concurrently, retrieved existing user")
                return user
            raise DatabaseError("Failed to create or retrieve user")
        except SQLAlchemyError as e:
            logger.error("Database error during race condition recovery", exc_info=True)
            raise DatabaseError("Failed to retrieve user after conflict") from e
        
    except SQLAlchemyError as e:
        logger.error("Database error managing user", exc_info=True)
        await db.rollback()
        raise DatabaseError("Failed to manage user") from e

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Get user by ID.
    
    Args:
        db: Database session
        user_id: User UUID
    
    Returns:
        User object or None if not found
    """
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error("Database error retrieving user", exc_info=True)  # Don't log PII (user_id)
        raise DatabaseError("Failed to retrieve user") from e

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Get user by email.
    
    Args:
        db: Database session
        email: User email address
    
    Returns:
        User object or None if not found
    """
    try:
        normalized_email = normalize_email(email)
        result = await db.execute(
            select(User).where(User.email == normalized_email)
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error("Database error retrieving user", exc_info=True)  # Don't log PII (email)
        raise DatabaseError("Failed to retrieve user") from e


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: Optional[str] = None,
) -> User:
    """
    Register a new user with email + password credentials.

    Raises ConflictError if the email is already taken.
    """
    normalized_email = normalize_email(email)
    try:
        result = await db.execute(
            select(User).where(User.email == normalized_email).with_for_update()
        )
        existing_user = result.scalar_one_or_none()
        if existing_user is not None:
            if existing_user.password_hash:
                raise ConflictError("A user with that email already exists")

            existing_user.password_hash = hash_password(password)
            if display_name and not existing_user.display_name:
                existing_user.display_name = display_name
            existing_user.is_active = True
            await db.commit()
            await db.refresh(existing_user)
            logger.info("Completed registration for existing passwordless user")
            return existing_user

        user = User(
            id=uuid.uuid4(),
            email=normalized_email,
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("User registered successfully")
        return user
    except IntegrityError:
        await db.rollback()
        raise ConflictError("A user with that email already exists")
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Database error during registration", exc_info=True)
        raise DatabaseError("Failed to register user") from e


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Verify email + password. Returns User on success, None on failure.
    """
    normalized_email = normalize_email(email)
    try:
        result = await db.execute(
            select(User).where(User.email == normalized_email, User.is_active)
        )
        user = result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error("Database error during authentication", exc_info=True)
        raise DatabaseError("Authentication query failed") from e

    if user is None:
        return None

    if not user.password_hash:
        local_identity = _match_legacy_local_user(user.email)
        if local_identity is None:
            return None

        locked_result = await db.execute(
            select(User).where(User.id == user.id).with_for_update()
        )
        locked_user = locked_result.scalar_one_or_none()
        if locked_user is None:
            return None
        if locked_user.password_hash:
            if verify_password(password, locked_user.password_hash):
                return locked_user
            return None

        legacy_user = fake_users_db.get(local_identity)
        if not legacy_user or not verify_password(password, legacy_user["hashed_password"]):
            return None

        locked_user.password_hash = hash_password(password)
        if hasattr(User, "role") and getattr(locked_user, "role", None) != legacy_user["role"]:
            locked_user.role = legacy_user["role"]
        await db.commit()
        await db.refresh(locked_user)
        logger.info("Migrated legacy passwordless user to password auth")
        return locked_user

    if not verify_password(password, user.password_hash):
        return None
    return user


def _match_legacy_local_user(email: Optional[str]) -> Optional[str]:
    normalized_email = normalize_email(email)
    if not normalized_email.endswith("@meetingintel.local"):
        return None

    username = normalized_email.split("@", 1)[0]
    if username in fake_users_db:
        return username
    return None
