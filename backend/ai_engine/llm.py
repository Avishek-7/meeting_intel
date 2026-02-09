from openai import OpenAI, RateLimitError, APIError, APITimeoutError, AuthenticationError
from core.config import settings
from core.exceptions import AIServiceError
from core.retry import with_exponential_backoff
from ai_engine.prompts.loader import load_prompt
import structlog
import time
import re
import json
from contextvars import ContextVar

logger = structlog.get_logger("ai_engine.llm")

# Track usage across multiple LLM calls in the same request
_usage_tracker: ContextVar[dict] = ContextVar("usage_tracker", default=None)

client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=settings.OPENAI_REQUEST_TIMEOUT,
)

SYSTEM_PROMPT = (
    "You are a precise, reliable AI assistant specialized in "
    "analyzing meeting transcripts."
)

DEFAULT_MODEL = settings.OPENAI_MODEL
FALLBACK_MODEL = settings.OPENAI_FALLBACK_MODEL
DEFAULT_TEMPERATURE = settings.OPENAI_TEMPERATURE
MAX_TOKENS = settings.OPENAI_MAX_TOKENS_PER_REQUEST
MAX_RETRIES = settings.OPENAI_MAX_RETRIES
BASE_WAIT_SECONDS = settings.OPENAI_RETRY_BASE_WAIT

# Create retry decorator for OpenAI calls with exponential backoff
_retry_openai = with_exponential_backoff(
    exception_types=(APIError, RateLimitError, APITimeoutError),
    max_retries=MAX_RETRIES,
    base_wait_seconds=BASE_WAIT_SECONDS,
)

@_retry_openai
def _call_openai(prompt: str) -> tuple[str, dict]:
    """Inner function with retry logic for transient errors.
    
    Includes timeout protection and token limits per request.
    Returns (content, usage_dict).
    """
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    
    usage = {
        "model": DEFAULT_MODEL,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    logger.info("llm_tokens", **usage)
    
    # Accumulate usage in context var if available
    tracker = _usage_tracker.get()
    if tracker is not None:
        tracker["model"] = DEFAULT_MODEL
        tracker["prompt_tokens"] = tracker.get("prompt_tokens", 0) + usage["prompt_tokens"]
        tracker["completion_tokens"] = tracker.get("completion_tokens", 0) + usage["completion_tokens"]
        tracker["total_tokens"] = tracker.get("total_tokens", 0) + usage["total_tokens"]
    
    return response.choices[0].message.content, usage

def generate_response(prompt: str) -> str:
    """
    Sends a prompt to OpenAI and returns the raw text response.

    This function is intentionally thin:
    - No business logic
    - No parsing
    - No orchestration
    
    Usage is tracked via context variable and accumulated across calls.
    """

    logger.info("llm_call_start", model=DEFAULT_MODEL, prompt_length=len(prompt))
    start_time = time.perf_counter()
    
    try:
        content, _ = _call_openai(prompt)
        latency = time.perf_counter() - start_time
        logger.info("llm_call_success", model=DEFAULT_MODEL, latency_seconds=round(latency, 3))
        
        if not content:
            logger.error("llm_call_empty_response", latency_seconds=round(latency, 3))
            raise ValueError("Empty response from LLM")
        
        return content.strip()
    
    except RateLimitError as e:
        latency = time.perf_counter() - start_time
        logger.warning("llm_call_rate_limit", latency_seconds=round(latency, 3), retries=MAX_RETRIES - 1)
        raise AIServiceError("LLM quota exceeded. Check your API plan and billing.") from e
    except AuthenticationError as e:
        latency = time.perf_counter() - start_time
        logger.error("llm_call_auth_error", latency_seconds=round(latency, 3))
        raise AIServiceError("LLM authentication failed. Check your API key.") from e
    except APITimeoutError as e:
        latency = time.perf_counter() - start_time
        logger.warning(
            "llm_call_timeout",
            timeout_seconds=settings.OPENAI_REQUEST_TIMEOUT,
            latency_seconds=round(latency, 3),
            max_retries=MAX_RETRIES,
        )
        raise AIServiceError("LLM request timed out. Request too complex or service slow.") from e
    except (APIError,) as e:
        latency = time.perf_counter() - start_time
        logger.warning("llm_call_api_error", latency_seconds=round(latency, 3))
        raise AIServiceError("LLM service temporarily unavailable after retries.") from e
    except Exception as e:
        latency = time.perf_counter() - start_time
        logger.error("llm_call_failed", latency_seconds=round(latency, 3))
        raise AIServiceError("Failed to generate LLM response") from e
    

def summarize_text(text: str, version: str = "v1") -> str:
    """
    Generates a concise meeting summary using a versioned prompt.
    Requests JSON structured output.
    """
    start_time = time.perf_counter()
    logger.info("summarize_start", version=version, text_length=len(text))
    
    try:
        prompt_template = load_prompt(f"summary_{version}")
        prompt = prompt_template.replace("{{text}}", text)
        
        # Request JSON output
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
    """
    Extracts action items from a meeting transcript.
    Requests JSON structured output with consistent schema.

    Returns a list of dicts with task, owner, due_date, and priority.
    """
    start_time = time.perf_counter()
    logger.info("extract_actions_start", version=version, text_length=len(text))
    
    prompt_template = load_prompt(f"action_items_{version}")
    prompt = prompt_template.replace("{{text}}", text)
    
    # Request JSON output with defined schema
    prompt += """\n\nRespond with JSON in format:
{
  "action_items": [
    {"task": "...", "owner": "...", "due_date": "...", "priority": "high|medium|low"},
    ...
  ]
}"""
    
    response = generate_response(prompt)
    json_payload = _extract_json_payload(response)

    try:
        data = json.loads(json_payload)
        items = data.get("action_items", [])
        
        if not isinstance(items, list):
            logger.error("extract_actions_json_list_invalid", version=version)
            return []
        
        # Validate and normalize
        validated = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                logger.warning("extract_actions_item_not_dict", version=version, index=idx)
                continue
            
            task = item.get("task", "").strip()
            if not task:
                logger.warning("extract_actions_empty_task", version=version, index=idx)
                continue
            
            owner = item.get("owner", "").strip() or "Not specified"
            due_date = item.get("due_date", "").strip() or "N/A"
            priority = item.get("priority", "medium").lower()
            
            # Validate priority
            if priority not in ["high", "medium", "low"]:
                logger.warning("extract_actions_invalid_priority", version=version, index=idx, priority=priority)
                priority = "medium"
            
            validated.append({
                "task": task.strip(",;"),
                "owner": owner,
                "due_date": due_date,
                "priority": priority
            })
        
        latency = time.perf_counter() - start_time
        logger.info("extract_actions_success", version=version, latency_seconds=round(latency, 3), count=len(validated))
        return validated
    
    except json.JSONDecodeError:
        latency = time.perf_counter() - start_time
        logger.warning("extract_actions_json_parse_failed", version=version, latency_seconds=round(latency, 3))
        return _parse_action_items_text(response)


def _extract_json_payload(response: str) -> str:
    """Extract a JSON object from an LLM response, handling code fences."""
    if not response:
        return "{}"

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", response, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    # Try to find the first JSON object in the response
    obj_match = re.search(r"\{[\s\S]*\}", response)
    if obj_match:
        return obj_match.group(0).strip()

    return response.strip()


def _parse_action_items_text(response: str) -> list[dict]:
    """Fallback regex-based parsing for non-JSON responses."""
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
            task = cleaned[:owner_match.start()].strip()
            rest = cleaned[owner_match.end():]
            deadline_match = deadline_pattern.search(rest)
            if deadline_match:
                owner = rest[:deadline_match.start()].strip()
                due_date = rest[deadline_match.end():].strip()
            else:
                owner = rest.strip()
        else:
            deadline_match = deadline_pattern.search(cleaned)
            if deadline_match:
                task = cleaned[:deadline_match.start()].strip()
                due_date = cleaned[deadline_match.end():].strip()
        
        items.append({
            "task": task.strip(",;"),
            "owner": owner or "Not specified",
            "due_date": due_date or "N/A",
            "priority": "medium"
        })
    
    logger.info("Parsed %d action items from text", len(items))
    return items
