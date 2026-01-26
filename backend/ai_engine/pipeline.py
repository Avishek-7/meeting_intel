from ai_engine.state import MeetingState
from ai_engine.preprocess import clean_text, chunk_text
from ai_engine.llm import summarize_text, extract_action_items
from ai_engine.validation import validate_summary, validate_action_items

MAX_LENGHTH = 3000

def analyze_meeting(transcript: str) -> MeetingState:
    state: MeetingState = {
        "transcript": transcript,
        "cleaned_text": "",
        "chunks": [],
        "summary": None,
        "action_items": []
    }

    # Preprocess the transcript
    state["cleaned_text"] = clean_text(transcript)

    # Decide strategy
    if len(state["cleaned_text"]) > MAX_LENGHTH:
        state["chunks"] = chunk_text(state["cleaned_text"])
        combined = " ".join(state["chunks"])
        summary = summarize_text(combined)
    else:
        summary = summarize_text(state["cleaned_text"])

    # Extract actions
    actions = extract_action_items(state["cleaned_text"])

    # Validate outputs
    state["summary"] = validate_summary(summary)
    state["action_items"] = validate_action_items(actions)

    return state