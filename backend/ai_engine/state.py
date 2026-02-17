from typing import TypedDict, Optional, NotRequired

class MeetingState(TypedDict):
    transcript: str
    cleaned_text: str
    chunks: list[str]
    summary: Optional[str]
    action_items: list[dict]
    status: str
    errors: list[dict]
    steps: NotRequired[dict]
    usage: NotRequired[dict]
    
