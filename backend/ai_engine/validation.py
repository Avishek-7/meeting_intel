
def validate_summary(summary: str) -> bool:
    return isinstance(summary, str) and len(summary) > 0

def validate_action_items(items: list[dict] | None) -> list[dict]:
    validated = []
    for item in items or []: 
        validated.append({
            "task": item.get("task", "").strip(),
            "owner": item.get("owner", "Not specified").strip(),
            "deadline": item.get("deadline", "N/A")
        })
    return validated
