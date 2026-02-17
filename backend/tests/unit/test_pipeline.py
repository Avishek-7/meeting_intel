from ai_engine.pipeline import analyze_meeting

def test_pipeline_happy_path(monkeypatch):
    # Mock LLM functions in the pipeline module's namespace
    # Note: extract_action_items should return a list of dicts with "task" key
    monkeypatch.setattr(
        "ai_engine.pipeline.summarize_text",
        lambda text, version="v1": "Mock summary"
    )
    monkeypatch.setattr(
        "ai_engine.pipeline.extract_action_items",
        lambda text: [{"task": "Mock action"}]
    )

    transcript = "John will prepare the report by Friday."

    result = analyze_meeting(transcript)

    assert result["summary"] == "Mock summary"
    assert len(result["action_items"]) == 1
    assert result["action_items"][0]["task"] == "Mock action"