
def validate_summary(summary: str) -> str:
    """Validate and return summary, ensuring it's a non-empty string."""
    if not isinstance(summary, str) or not summary.strip():
        return "No summary available"
    return summary.strip()

def validate_action_items(items: list[dict] | None) -> list[dict]:
    """Validate action items and apply defaults for missing fields."""
    validated = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        
        task = item.get("task", "").strip()
        if not task:  # Skip empty tasks
            continue
            
        validated.append({
            "task": task,
            "owner": item.get("owner") or "Not specified",
            "due_date": item.get("due_date") or "N/A"
        })
    return validated
