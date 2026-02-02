from sqlalchemy import Column, Integer, ForeignKey, Text, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

Base = declarative_base()

class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    transcript_text = Column(Text, nullable=False)
    transcript_hash = Column(String(64), unique=True, nullable=False, index=True)
    
    summary_text = Column(Text, nullable=False)
    action_items = Column(JSONB, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())