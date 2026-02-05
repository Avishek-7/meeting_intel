from ai_engine.state import MeetingState
from ai_engine.preprocess import clean_text, chunk_text
from ai_engine.llm import summarize_text, extract_action_items, _usage_tracker
from ai_engine.validation import validate_summary, validate_action_items
import structlog
import time

logger = structlog.get_logger("ai_engine.pipeline")

MAX_LENGTH = 3000

def analyze_meeting(transcript: str) -> MeetingState:
    start_time = time.perf_counter()
    logger.info("analyze_meeting_start", transcript_length=len(transcript))
    
    # Initialize usage tracker for this analysis
    usage_data = {
        "model": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    token = _usage_tracker.set(usage_data)
    
    state: MeetingState = {
        "transcript": transcript,
        "cleaned_text": "",
        "chunks": [],
        "summary": None,
        "action_items": [],
        "usage": usage_data
    }

    try:
        # Preprocess the transcript
        preprocess_start = time.perf_counter()
        state["cleaned_text"] = clean_text(transcript)
        preprocess_duration = time.perf_counter() - preprocess_start
        logger.info("preprocess_complete", duration_seconds=round(preprocess_duration, 3), cleaned_length=len(state["cleaned_text"]))

        # Decide strategy
        if len(state["cleaned_text"]) > MAX_LENGTH:
            chunk_start = time.perf_counter()
            logger.info("chunking_enabled", max_length=MAX_LENGTH)
            state["chunks"] = chunk_text(state["cleaned_text"])
            chunk_duration = time.perf_counter() - chunk_start
            logger.info("chunking_complete", duration_seconds=round(chunk_duration, 3), chunk_count=len(state["chunks"]))
            chunk_summaries = [summarize_text(chunk) for chunk in state["chunks"]]
            summary = summarize_text(" ".join(chunk_summaries))
        else:
            summary = summarize_text(state["cleaned_text"])

        # Extract actions
        actions = extract_action_items(state["cleaned_text"])

        # Validate outputs
        state["summary"] = validate_summary(summary)
        state["action_items"] = validate_action_items(actions)

        total_duration = time.perf_counter() - start_time
        logger.info("analyze_meeting_complete", duration_seconds=round(total_duration, 3), action_count=len(state["action_items"]), summary_length=len(state["summary"] or ""))
        
        # Log aggregated usage
        logger.info("total_llm_usage", **usage_data)
        
        return state
    
    except Exception:
        total_duration = time.perf_counter() - start_time
        logger.error("analyze_meeting_failed", duration_seconds=round(total_duration, 3))
        raise
    finally:
        _usage_tracker.reset(token)