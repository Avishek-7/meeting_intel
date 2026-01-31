import pytest
from fastapi.testclient import TestClient
from main import app
from core.security import create_access_token

client = TestClient(app)

@pytest.mark.skip(reason="Integration test requires database connection")
def test_analyze_meeting_endpoint(monkeypatch):
    # Create a valid auth token for an existing user
    token = create_access_token({"sub": "avishek"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Mock the analyze_meeting function in the pipeline module
    monkeypatch.setattr(
        "services.meeting_service.analyze_meeting",
        lambda transcript: {
            "transcript": transcript,
            "cleaned_text": transcript,
            "chunks": [],
            "summary": "Test summary",
            "action_items": []
        }
    )

    payload = {
        "transcript": "We discussed deadlines. John will prepare the report."
    }

    response = client.post("/meetings/analyze", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "action_items" in data
    assert data["summary"] == "Test summary"

