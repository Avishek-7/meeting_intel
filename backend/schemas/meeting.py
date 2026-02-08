from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum

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
