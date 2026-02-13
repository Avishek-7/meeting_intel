from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from models.base import Base
from core.rbac import Role

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True, index=True)
    # Role determines permissions for user. Must be one of: "admin", "user"
    # Defaults to "user" - regular application access
    # "admin" - full platform access including analytics and user management
    role = Column(String(50), nullable=False, default=Role.USER.value, server_default=Role.USER.value)
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
