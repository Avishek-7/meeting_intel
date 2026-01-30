import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def validate_summary(summary: str) -> str:
    """Validate and return summary, ensuring it's a non-empty string."""
    if not isinstance(summary, str):
        logger.error("Summary is not a string: %s", type(summary))
        raise ValueError("Summary must be a string")
    
    summary = summary.strip()
    if not summary:
        logger.error("Summary is empty")
        raise ValueError("Summary cannot be empty")
    
    if len(summary) < 10:
        logger.warning("Summary is very short: %d chars", len(summary))
    
    return summary

def validate_action_items(items: list[dict] | None) -> list[dict]:
    """Validate action items with consistent schema.
    
    Ensures all action items have required fields and valid types.
    """
    if not items:
        logger.debug("No action items provided")
        return []
    
    if not isinstance(items, list):
        logger.error("Action items is not a list: %s", type(items))
        raise ValueError("Action items must be a list")
    
    validated = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict action item at index %d: %s", idx, type(item))
            continue
        
        task = item.get("task", "").strip()
        if not task:
            logger.warning("Skipping action item at index %d: empty task", idx)
            continue
        
        # Validate task length
        if len(task) > 500:
            logger.warning("Truncating task at index %d (length: %d)", idx, len(task))
            task = task[:500]
        
        owner = str(item.get("owner") or "").strip() or "Not specified"
        due_date = str(item.get("due_date") or "").strip() or "N/A"
        priority_raw = item.get("priority")
        priority = str(priority_raw).lower() if priority_raw else "medium"
        
        # Validate priority
        if priority not in ["high", "medium", "low"]:
            logger.warning("Invalid priority at index %d: %s, using medium", idx, priority)
            priority = "medium"
        
        validated.append({
            "task": task,
            "owner": owner,
            "due_date": due_date,
            "priority": priority
        })
    
    logger.info("Validated %d action items", len(validated))
    return validated

def parse_json_response(response: str) -> dict:
    """Parse JSON from LLM response with fallback to raw parsing.
    
    Returns structured dict with summary and action_items.
    """
    try:
        # Try direct JSON parse
        data = json.loads(response)
        
        if not isinstance(data, dict):
            logger.error("JSON response is not a dict: %s", type(data))
            raise ValueError("Response must be a JSON object")
        
        if "summary" not in data or "action_items" not in data:
            logger.error("Missing required fields in JSON response")
            raise ValueError("Response must contain 'summary' and 'action_items' fields")
        
        return {
            "summary": validate_summary(data["summary"]),
            "action_items": validate_action_items(data.get("action_items", []))
        }
    
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response: %s", e)
        raise ValueError("Response is not valid JSON") from e
    except (ValueError, TypeError) as e:
        logger.error("Invalid response structure: %s", e)
        raise
