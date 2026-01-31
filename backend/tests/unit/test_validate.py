from ai_engine.validation import validate_summary, validate_action_items

def test_validate_summary_fallback():
    # Test that empty string returns fallback
    try:
        validate_summary(None)
        assert False, "Should raise ValueError for None"
    except ValueError:
        pass  # Expected behavior

def test_validate_action_items_defaults():
    raw_items = [
        {"task": "Prepare report"},
        {"task": "Send emails", "owner": "Alice"},
    ]

    validated = validate_action_items(raw_items)

    assert validated[0]["owner"] == "Not specified"
    assert validated[0]["due_date"] == "N/A"
    assert validated[1]["owner"] == "Alice"