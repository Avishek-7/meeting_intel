from ai_engine.state import MeetingState
from ai_engine.preprocess import clean_text, chunk_text
from ai_engine.llm import summarize_text, extract_action_items as llm_extract_action_items, _usage_tracker
from ai_engine.validation import validate_summary, validate_action_items
import structlog
import time
from typing import Any, Callable

logger = structlog.get_logger("ai_engine.pipeline")

MAX_LENGTH = 3000

def generate_summary(transcript: str) -> str:
    try:
        cleaned_text = clean_text(transcript)
        summary_source_text = cleaned_text

        if len(cleaned_text) > MAX_LENGTH:
            logger.info("chunking_enabled", max_length=MAX_LENGTH)
            chunks = chunk_text(cleaned_text)
            if chunks:
                chunk_summaries = [summarize_text(chunk) for chunk in chunks]
                combined_summaries = " ".join(chunk_summaries)
                if len(combined_summaries) > MAX_LENGTH:
                    logger.warning("combined_summaries_exceed_max", length=len(combined_summaries))
                    combined_summaries = combined_summaries[:MAX_LENGTH]
                summary_source_text = combined_summaries

        summary = summarize_text(summary_source_text)
        return validate_summary(summary)
    except Exception as exc:
        logger.error("generate_summary_failed", error_type=type(exc).__name__, error_message=str(exc), exc_info=True)
        try:
            fallback = clean_text(transcript)[:500].strip() or "Summary unavailable."
        except Exception:
            fallback = transcript[:500].strip() if transcript else "Summary unavailable."
        return fallback


def extract_action_items(transcript: str) -> list[dict]:
    try:
        cleaned_text = clean_text(transcript)
        actions = llm_extract_action_items(cleaned_text)
        return validate_action_items(actions)
    except Exception as exc:
        logger.error("extract_action_items_failed", error_type=type(exc).__name__, error_message=str(exc), exc_info=True)
        return []

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
        "status": "ok",
        "errors": [],
        "steps": {},
        "usage": usage_data,
    }

    def _run_step(
        name: str,
        func: Callable[[], Any],
        *,
        allow_failure: bool = True,
        fallback: Any = None,
        log_fields: dict | None = None,
    ) -> tuple[bool, Any]:
        log_fields = log_fields or {}
        logger.info("step_start", step=name, **log_fields)
        start_time = time.perf_counter()

        try:
            result = func()
            duration = time.perf_counter() - start_time
            state["steps"][name] = {
                "ok": True,
                "duration_seconds": round(duration, 3),
            }
            logger.info("step_complete", step=name, duration_seconds=round(duration, 3), **log_fields)
            return True, result
        except Exception as exc:
            duration = time.perf_counter() - start_time
            error = {
                "step": name,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "duration_seconds": round(duration, 3),
            }
            state["errors"].append(error)
            state["steps"][name] = {
                "ok": False,
                "duration_seconds": round(duration, 3),
            }
            logger.error(
                "step_failed",
                step=name,
                duration_seconds=round(duration, 3),
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
                **log_fields,
            )
            if not allow_failure:
                raise
            return False, fallback() if callable(fallback) else fallback

    try:
        _, cleaned_text = _run_step(
            "preprocess",
            lambda: clean_text(transcript),
            fallback=transcript,
            log_fields={"transcript_length": len(transcript)},
        )
        state["cleaned_text"] = cleaned_text or ""

        summary_source_text = state["cleaned_text"]
        if len(state["cleaned_text"]) > MAX_LENGTH:
            logger.info("chunking_enabled", max_length=MAX_LENGTH)
            _, chunks = _run_step(
                "chunk_text",
                lambda: chunk_text(state["cleaned_text"]),
                fallback=[],
                log_fields={"cleaned_length": len(state["cleaned_text"])},
            )
            state["chunks"] = chunks or []

            if state["chunks"]:
                _, chunk_summaries = _run_step(
                    "summarize_chunks",
                    lambda: [summarize_text(chunk) for chunk in state["chunks"]],
                    fallback=[],
                    log_fields={"chunk_count": len(state["chunks"])},
                )
                combined_summaries = " ".join(chunk_summaries or [])
                if combined_summaries:
                    if len(combined_summaries) > MAX_LENGTH:
                        logger.warning("combined_summaries_exceed_max", length=len(combined_summaries))
                        combined_summaries = combined_summaries[:MAX_LENGTH]
                    summary_source_text = combined_summaries

        _, summary = _run_step(
            "summarize",
            lambda: summarize_text(summary_source_text),
            fallback=None,
            log_fields={"source_length": len(summary_source_text)},
        )

        action_source_text = summary or state["cleaned_text"]
        _, actions = _run_step(
            "extract_action_items",
            lambda: extract_action_items(action_source_text),
            fallback=[],
            log_fields={"source_length": len(action_source_text)},
        )

        _, validated_summary = _run_step(
            "validate_summary",
            lambda: validate_summary(summary) if summary else None,
            fallback=None,
        )
        if not validated_summary:
            fallback_summary = (state["cleaned_text"] or "")[:500].strip() or "Summary unavailable."
            state["summary"] = fallback_summary
            state["errors"].append({
                "step": "summary_fallback",
                "error_type": "FallbackUsed",
                "error_message": "Summary missing; fallback applied.",
                "duration_seconds": 0.0,
            })
            logger.warning("summary_fallback_used")
        else:
            state["summary"] = validated_summary
        state["action_items"] = actions

        if state["errors"]:
            if state["summary"] or state["action_items"]:
                state["status"] = "partial"
            else:
                state["status"] = "failed"

        total_duration = time.perf_counter() - start_time
        logger.info(
            "analyze_meeting_complete",
            duration_seconds=round(total_duration, 3),
            action_count=len(state["action_items"]),
            summary_length=len(state["summary"] or ""),
            status=state["status"],
            error_count=len(state["errors"]),
        )

        logger.info("total_llm_usage", **usage_data)
    except Exception as exc:
        total_duration = time.perf_counter() - start_time
        state["status"] = "failed"
        state["errors"].append({
            "step": "pipeline",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "duration_seconds": round(total_duration, 3),
        })
        logger.error("analyze_meeting_failed", duration_seconds=round(total_duration, 3), exc_info=True)
    finally:
        _usage_tracker.reset(token)
    return state