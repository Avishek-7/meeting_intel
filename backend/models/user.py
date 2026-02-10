from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from models.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True, index=True)
    role = Column(String(50), nullable=True, default="user", server_default="user")
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
