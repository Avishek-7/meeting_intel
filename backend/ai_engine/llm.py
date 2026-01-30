from openai import OpenAI, RateLimitError, APIError, APITimeoutError, AuthenticationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from core.config import settings
from core.exceptions import AIServiceError
from ai_engine.prompts.loader import load_prompt
import logging
import time
import re
import json

logger = logging.getLogger(__name__)

RETRY_ERRORS = (
    APIError,
    RateLimitError,
    APITimeoutError,
)

client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=settings.OPENAI_REQUEST_TIMEOUT,
)

SYSTEM_PROMPT = (
    "You are a precise, reliable AI assistant specialized in "
    "analyzing meeting transcripts."
)

DEFAULT_MODEL = settings.OPENAI_MODEL
DEFAULT_TEMPERATURE = settings.OPENAI_TEMPERATURE
MAX_TOKENS = settings.OPENAI_MAX_TOKENS_PER_REQUEST
MAX_RETRIES = settings.OPENAI_MAX_RETRIES
BASE_WAIT_SECONDS = settings.OPENAI_RETRY_BASE_WAIT

@retry(
    retry=retry_if_exception_type(RETRY_ERRORS),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=BASE_WAIT_SECONDS, max=10),
)
def _call_openai(prompt: str) -> str:
    """Inner function with retry logic for transient errors.
    
    Includes timeout protection and token limits per request.
    """
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=MAX_TOKENS,
        timeout=settings.OPENAI_REQUEST_TIMEOUT,
    )
    return response.choices[0].message.content

def generate_response(prompt: str) -> str:
    """
    Sends a prompt to OpenAI and returns the raw text response.

    This function is intentionally thin:
    - No business logic
    - No parsing
    - No orchestration 
    """

    logger.info("Calling LLM with model=%s, prompt_length=%s", DEFAULT_MODEL, len(prompt))
    start_time = time.perf_counter()
    
    try:
        content = _call_openai(prompt)
        duration = time.perf_counter() - start_time
        logger.info("LLM call completed in %.2fs", duration)
        
        if not content:
            logger.error("LLM returned empty response content.")
            raise ValueError("Empty response from LLM")
        
        return content.strip()
    
    except RateLimitError as e:
        # Permanent quota error - don't retry
        logger.warning("LLM quota exceeded (permanent error).", exc_info=True)
        raise AIServiceError("LLM quota exceeded. Check your API plan and billing.") from e
    except AuthenticationError as e:
        # Permanent auth error - don't retry
        logger.error("LLM authentication failed.", exc_info=True)
        raise AIServiceError("LLM authentication failed. Check your API key.") from e
    except APITimeoutError as e:
        # Request timeout - transient but worth logging
        logger.warning(f"LLM request timeout after {settings.OPENAI_REQUEST_TIMEOUT}s (retry limit: {MAX_RETRIES}).", exc_info=True)
        raise AIServiceError("LLM request timed out. Request too complex or service slow.") from e
    except (APIError,) as e:
        # Transient errors already retried by decorator, still failing
        logger.warning("LLM transient error persisted after retries.", exc_info=True)
        raise AIServiceError("LLM service temporarily unavailable after retries.") from e
    except Exception as e:
        logger.error("OpenAI LLM call failed.", exc_info=True)
        raise AIServiceError("Failed to generate LLM response") from e
    

def summarize_text(text: str, version: str = "v1") -> str:
    """
    Generates a concise meeting summary using a versioned prompt.
    Requests JSON structured output.
    """
    logger.info("Generating summary with prompt version=%s, text_length=%s", version, len(text))
    prompt_template = load_prompt(f"summary_{version}")
    prompt = prompt_template.replace("{{text}}", text)
    
    # Request JSON output
    prompt += "\n\nRespond with JSON in format: {\"summary\": \"<summary text>\"}"
    
    response = generate_response(prompt)
    
    try:
        data = json.loads(response)
        return data.get("summary", response.strip())
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Summary response not valid JSON, using raw text")
        return response.strip()


def extract_action_items(text: str, version: str = "v1") -> list[dict]:
    """
    Extracts action items from a meeting transcript.
    Requests JSON structured output with consistent schema.

    Returns a list of dicts with task, owner, due_date, and priority.
    """
    logger.info("Extracting action items with prompt version=%s, text_length=%s", version, len(text))
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

    try:
        data = json.loads(response)
        items = data.get("action_items", [])
        
        if not isinstance(items, list):
            logger.error("action_items is not a list in JSON response")
            return []
        
        # Validate and normalize
        validated = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict item at index %d", idx)
                continue
            
            task = item.get("task", "").strip()
            if not task:
                logger.warning("Skipping item at index %d: empty task", idx)
                continue
            
            owner = item.get("owner", "").strip() or "Not specified"
            due_date = item.get("due_date", "").strip() or "N/A"
            priority = item.get("priority", "medium").lower()
            
            # Validate priority
            if priority not in ["high", "medium", "low"]:
                logger.warning("Invalid priority at index %d: %s, using medium", idx, priority)
                priority = "medium"
            
            validated.append({
                "task": task.strip(",;"),
                "owner": owner,
                "due_date": due_date,
                "priority": priority
            })
        
        logger.info("Extracted %d action items from JSON", len(validated))
        return validated
    
    except json.JSONDecodeError:
        logger.warning("Action items response not valid JSON, falling back to regex parsing")
        return _parse_action_items_text(response)


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
