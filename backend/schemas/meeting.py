from pydantic import BaseModel, Field
from typing import List, Optional

class MeetingRequest(BaseModel):
    title: Optional[str] = None
    transcript: str = Field(..., description="The transcript of the meeting", min_length=10)

class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None

class MeetingResponse(BaseModel):
    summary: str
    action_items: List[ActionItem]
