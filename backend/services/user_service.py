from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
from models.user import User
from core.exceptions import DatabaseError
import uuid
import logging

logger = logging.getLogger(__name__)

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
        # Try to find existing user
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            logger.info(f"Found existing user with id: {user.id}")
            return user
        
        # Create new user
        user = User(
            id=uuid.uuid4(),
            email=email
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Created new user with id: {user.id}")
        return user
        
    except IntegrityError:
        # Handle race condition - another request created the user
        await db.rollback()
        try:
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if user:
                logger.info(f"User created concurrently, retrieved id: {user.id}")
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
