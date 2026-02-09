from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime
from decimal import Decimal

class PriorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ActionItem(BaseModel):
    task: str = Field(..., min_length=1, description="Action item task description")
    owner: str = Field(default="Not specified", description="Person responsible")
    due_date: str = Field(default="N/A", description="Due date or deadline")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Priority level")
    
    @field_validator('task')
    @classmethod
    def task_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Task cannot be empty")
        return v.strip()

class MeetingRequest(BaseModel):
    title: Optional[str] = None
    transcript: str = Field(..., description="The transcript of the meeting", min_length=10)

class MeetingSummaryBase(BaseModel):
    summary: str = Field(..., min_length=1, description="Meeting summary")
    action_items: List[ActionItem] = Field(default_factory=list, description="Extracted action items")

    @field_validator('summary')
    @classmethod
    def summary_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Summary cannot be empty")
        return v.strip()

class MeetingResponse(MeetingSummaryBase):
    pass

class MeetingJobResult(MeetingSummaryBase):
    meeting_id: Optional[str] = None



class MeetingJobEnqueueResponse(BaseModel):
    job_id: str
    status: str = Field(default="queued")

class MeetingJobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[MeetingJobResult] = None
    error: Optional[str] = None


# Meeting History & Analytics Schemas

class MeetingMetadata(BaseModel):
    id: str = Field(..., description="Meeting UUID")
    created_at: datetime = Field(..., description="Meeting creation timestamp")
    summary_preview: str = Field(..., description="First 200 chars of summary")
    action_count: int = Field(..., description="Number of action items")
    total_tokens: int = Field(default=0, description="Total tokens used")
    estimated_cost: Decimal = Field(default=Decimal("0.00"), description="Estimated cost in USD")

    class Config:
        json_encoders = {Decimal: str, datetime: str}


class MeetingDetail(BaseModel):
    id: str
    created_at: datetime
    summary: str
    action_items: List[ActionItem]
    total_tokens: int
    estimated_cost: Decimal
    model_name: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    class Config:
        json_encoders = {Decimal: str, datetime: str}
        protected_namespaces = ()


class UserStats(BaseModel):
    total_cost: Decimal
    total_tokens: int
    total_meetings: int
    cost_by_model: Dict[str, Decimal]
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    class Config:
        json_encoders = {Decimal: str, datetime: str}


class DailyStats(BaseModel):
    date: str
    cost: Decimal
    token_count: int
    meeting_count: int

    class Config:
        json_encoders = {Decimal: str}


class GlobalStats(BaseModel):
    total_cost: Decimal
    total_users: int
    total_meetings: int
    total_tokens: int
    cost_by_model: Dict[str, Decimal]
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    class Config:
        json_encoders = {Decimal: str, datetime: str}


class PaginatedMeetings(BaseModel):
    items: List[MeetingMetadata]
    total: int
    limit: int
    offset: int
    has_more: bool
