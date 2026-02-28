from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
from models.user import User
from core.exceptions import DatabaseError
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
