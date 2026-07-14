from contextvars import ContextVar
import json
import re
import time

import structlog
from google import genai
from google.genai import types
from google.genai.errors import (
    APIError,
    ClientError,
    ServerError,
)

from ai_engine.prompts.loader import load_prompt
from core.config import settings
from core.exceptions import AIServiceError
from core.retry import with_exponential_backoff

logger = structlog.get_logger("ai_engine.google_llm")

_usage_tracker: ContextVar[dict] = ContextVar("usage_tracker", default=None)

# Initialize client only if API key is configured
client = None
if settings.GOOGLE_API_KEY:
    client = genai.Client(
        api_key=settings.GOOGLE_API_KEY,
    )

SYSTEM_PROMPT = (
    "You are a precise, reliable AI assistant specialized in "
    "analyzing meeting transcripts."
)

DEFAULT_MODEL = settings.GOOGLE_MODEL
FALLBACK_MODEL = settings.GOOGLE_FALLBACK_MODEL
DEFAULT_TEMPERATURE = settings.GOOGLE_TEMPERATURE
MAX_TOKENS = settings.GOOGLE_MAX_TOKENS_PER_REQUEST
MAX_RETRIES = settings.GOOGLE_MAX_RETRIES
BASE_WAIT_SECONDS = settings.GOOGLE_RETRY_BASE_WAIT

_retry_google = with_exponential_backoff(
    exception_types=(APIError, ClientError, ServerError),
    max_attempts=MAX_RETRIES,
    base_wait_seconds=BASE_WAIT_SECONDS,
)


@_retry_google
def _call_google_api(prompt: str) -> tuple[str, dict]:
    if client is None:
        raise AIServiceError("Google API client not initialized. GOOGLE_API_KEY may not be configured.")
    
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=DEFAULT_TEMPERATURE,
            max_output_tokens=MAX_TOKENS,
        ),
    )

    usage = {}
    usage_meta = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
    if usage_meta:
        prompt_tokens = getattr(usage_meta, "prompt_token_count", None)
        if prompt_tokens is None:
            prompt_tokens = getattr(usage_meta, "prompt_tokens", 0)

        completion_tokens = getattr(usage_meta, "candidates_token_count", None)
        if completion_tokens is None:
            completion_tokens = getattr(usage_meta, "completion_tokens", 0)

        total_tokens = getattr(usage_meta, "total_token_count", None)
        if total_tokens is None:
            total_tokens = getattr(usage_meta, "total_tokens", 0)

        usage = {
            "model": DEFAULT_MODEL,
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
            "total_tokens": total_tokens or 0,
        }
        logger.info("llm_tokens", **usage)

    tracker = _usage_tracker.get()
    if tracker is not None and usage:
        tracker["model"] = DEFAULT_MODEL
        tracker["prompt_tokens"] = tracker.get("prompt_tokens", 0) + usage["prompt_tokens"]
        tracker["completion_tokens"] = tracker.get("completion_tokens", 0) + usage["completion_tokens"]
        tracker["total_tokens"] = tracker.get("total_tokens", 0) + usage["total_tokens"]

    content = (getattr(response, "text", None) or "").strip()
    if not content:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
            text_parts = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
            content = "\n".join(text_parts).strip()

    if not content:
        raise AIServiceError("Google API returned a non-text or empty response")

    return content, usage


def generate_response(prompt: str) -> str:
    logger.info("llm_call_start", model=DEFAULT_MODEL, prompt_length=len(prompt))
    start_time = time.perf_counter()

    try:
        content, _ = _call_google_api(prompt)
        latency = time.perf_counter() - start_time
        logger.info("llm_call_success", model=DEFAULT_MODEL, latency_seconds=round(latency, 3))

        if not content:
            logger.error("llm_call_empty_response", latency_seconds=round(latency, 3))
            raise ValueError("Empty response from LLM")

        return content.strip()

    except ClientError as e:
        latency = time.perf_counter() - start_time
        # ClientError can include auth, rate limit, and timeout issues
        error_msg = str(e).lower()
        if "auth" in error_msg or "api key" in error_msg:
            logger.error("llm_call_auth_error", latency_seconds=round(latency, 3))
            raise AIServiceError("LLM authentication failed. Check your API key.") from e
        elif "rate" in error_msg or "quota" in error_msg:
            logger.warning("llm_call_rate_limit", latency_seconds=round(latency, 3), retries=MAX_RETRIES - 1)
            raise AIServiceError("LLM quota exceeded. Check your API plan and billing.") from e
        elif "timeout" in error_msg:
            logger.warning(
                "llm_call_timeout",
                timeout_seconds=settings.GOOGLE_API_TIMEOUT_SECONDS,
                latency_seconds=round(latency, 3),
                max_retries=MAX_RETRIES,
            )
            raise AIServiceError("LLM request timed out. Request too complex or service slow.") from e
        else:
            logger.warning("llm_call_client_error", latency_seconds=round(latency, 3))
            raise AIServiceError("LLM client error after retries.") from e
    except ServerError as e:
        latency = time.perf_counter() - start_time
        logger.warning("llm_call_server_error", latency_seconds=round(latency, 3))
        raise AIServiceError("LLM service temporarily unavailable after retries.") from e
    except APIError as e:
        latency = time.perf_counter() - start_time
        logger.warning("llm_call_api_error", latency_seconds=round(latency, 3))
        raise AIServiceError("LLM API error after retries.") from e
    except Exception as e:
        latency = time.perf_counter() - start_time
        logger.error("llm_call_failed", latency_seconds=round(latency, 3))
        raise AIServiceError("Failed to generate LLM response") from e


def summarize_text(text: str, version: str = "v1") -> str:
    start_time = time.perf_counter()
    logger.info("summarize_start", version=version, text_length=len(text))

    try:
        prompt_template = load_prompt(f"summary_{version}")
        prompt = prompt_template.replace("{{text}}", text)
        prompt += "\n\nRespond with JSON in format: {\"summary\": \"<summary text>\"}"

        response = generate_response(prompt)

        try:
            data = json.loads(response)
            result = data.get("summary", response.strip())
        except (json.JSONDecodeError, AttributeError):
            logger.warning("summarize_json_parse_failed", version=version)
            result = response.strip()

        latency = time.perf_counter() - start_time
        logger.info("summarize_success", version=version, latency_seconds=round(latency, 3), summary_length=len(result))
        return result
    except Exception:
        latency = time.perf_counter() - start_time
        logger.error("summarize_failed", version=version, latency_seconds=round(latency, 3))
        raise


def extract_action_items(text: str, version: str = "v1") -> list[dict]:
    start_time = time.perf_counter()
    logger.info("extract_actions_start", version=version, text_length=len(text))

    prompt_template = load_prompt(f"action_items_{version}")
    prompt = prompt_template.replace("{{text}}", text)
    prompt += """\n\nRespond with JSON in format:
{
  \"action_items\": [
    {\"task\": \"...\", \"owner\": \"...\", \"due_date\": \"...\", \"priority\": \"high|medium|low\"},
    ...
  ]
}"""

    try:
        response = generate_response(prompt)
    except Exception:
        latency = time.perf_counter() - start_time
        logger.error("extract_actions_failed", version=version, latency_seconds=round(latency, 3))
        raise

    json_payload = _extract_json_payload(response)

    try:
        data = json.loads(json_payload)
        items = data.get("action_items", [])

        if not isinstance(items, list):
            latency = time.perf_counter() - start_time
            logger.error("extract_actions_json_list_invalid", version=version, latency_seconds=round(latency, 3))
            return []

        validated = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                logger.warning("extract_actions_item_not_dict", version=version, index=idx)
                continue

            task = (item.get("task") or "").strip()
            if not task:
                logger.warning("extract_actions_empty_task", version=version, index=idx)
                continue

            owner = (item.get("owner") or "").strip() or "Not specified"
            due_date = (item.get("due_date") or "").strip() or "N/A"
            priority = (item.get("priority") or "medium").lower()

            if priority not in ["high", "medium", "low"]:
                logger.warning("extract_actions_invalid_priority", version=version, index=idx, priority=priority)
                priority = "medium"

            validated.append(
                {
                    "task": task.strip(",;"),
                    "owner": owner,
                    "due_date": due_date,
                    "priority": priority,
                }
            )

        latency = time.perf_counter() - start_time
        logger.info("extract_actions_success", version=version, latency_seconds=round(latency, 3), count=len(validated))
        return validated

    except json.JSONDecodeError:
        latency = time.perf_counter() - start_time
        logger.warning("extract_actions_json_parse_failed", version=version, latency_seconds=round(latency, 3))
        return _parse_action_items_text(response)


def _extract_json_payload(response: str) -> str:
    if not response:
        return "{}"

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", response, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    start = response.find("{")
    if start != -1:
        depth = 0
        for index in range(start, len(response)):
            char = response[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return response[start : index + 1].strip()

    obj_match = re.search(r"\{[\s\S]*\}", response)
    if obj_match:
        return obj_match.group(0).strip()

    return response.strip()


def _parse_action_items_text(response: str) -> list[dict]:
    owner_pattern = re.compile(r"owner:\s*", re.IGNORECASE)
    deadline_pattern = re.compile(r"deadline:\s*", re.IGNORECASE)
    items = []

    for line in response.splitlines():
        cleaned = line.lstrip("-•* ").strip()
        if not cleaned:
            continue

        task = cleaned
        owner = None
        due_date = None

        owner_match = owner_pattern.search(cleaned)
        if owner_match:
            task = cleaned[: owner_match.start()].strip()
            rest = cleaned[owner_match.end() :]
            deadline_match = deadline_pattern.search(rest)
            if deadline_match:
                owner = rest[: deadline_match.start()].strip()
                due_date = rest[deadline_match.end() :].strip()
            else:
                owner = rest.strip()
        else:
            deadline_match = deadline_pattern.search(cleaned)
            if deadline_match:
                task = cleaned[: deadline_match.start()].strip()
                due_date = cleaned[deadline_match.end() :].strip()

        items.append(
            {
                "task": task.strip(",;"),
                "owner": owner or "Not specified",
                "due_date": due_date or "N/A",
                "priority": "medium",
            }
        )

    logger.info("parse_action_items_text_complete", count=len(items))
    return items
