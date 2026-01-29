from ai_engine.state import MeetingState
from ai_engine.preprocess import clean_text, chunk_text
from ai_engine.llm import summarize_text, extract_action_items
from ai_engine.validation import validate_summary, validate_action_items
import logging

logger = logging.getLogger(__name__)

MAX_LENGHTH = 3000

def analyze_meeting(transcript: str) -> MeetingState:
    logger.info("Starting meeting analysis pipeline.")
    state: MeetingState = {
        "transcript": transcript,
        "cleaned_text": "",
        "chunks": [],
        "summary": None,
        "action_items": []
    }

    # Preprocess the transcript
    state["cleaned_text"] = clean_text(transcript)
    logger.info("Transcript cleaned. Length: %d", len(state["cleaned_text"]))

    # Decide strategy
    if len(state["cleaned_text"]) > MAX_LENGHTH:
        logger.info("Transcript exceeds max length, chunking enabled.")
        state["chunks"] = chunk_text(state["cleaned_text"])
        combined = " ".join(state["chunks"])
        summary = summarize_text(combined)
    else:
        summary = summarize_text(state["cleaned_text"])
    logger.info("Summary generated.")

    # Extract actions
    actions = extract_action_items(state["cleaned_text"])
    logger.info("Extracted %d action items.", len(actions))

    # Validate outputs
    state["summary"] = validate_summary(summary)
    state["action_items"] = validate_action_items(actions)

    logger.info("Meeting analysis pipeline completed.")
    return state