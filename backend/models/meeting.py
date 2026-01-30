from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

Base = declarative_base()

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True)
    transcript = Column(Text, nullable=False, unique=True)
    summary = Column(Text, nullable=True)

    action_items = relationship(
        "ActionItem",
        back_populates="meeting",
        cascade="all, delete-orphan"
    )


class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(
        Integer, 
        ForeignKey("meetings.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    meeting = relationship("Meeting", back_populates="action_items")