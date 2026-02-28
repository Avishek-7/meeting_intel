import json

from scripts import compare_llm_responses


def test_run_provider_call_success():
    result = compare_llm_responses._run_provider_call(
        provider_name="openai",
        fn=lambda prompt: f"ok:{prompt}",
        payload="hello",
    )

    assert result["provider"] == "openai"
    assert result["ok"] is True
    assert result["result"] == "ok:hello"
    assert result["error"] is None
    assert isinstance(result["latency_seconds"], float)


def test_run_provider_call_failure():
    def failing(_prompt: str):
        raise RuntimeError("boom")

    result = compare_llm_responses._run_provider_call(
        provider_name="google",
        fn=failing,
        payload="hello",
    )

    assert result["provider"] == "google"
    assert result["ok"] is False
    assert result["result"] is None
    assert result["error"]["type"] == "RuntimeError"
    assert result["error"]["message"] == "boom"
    assert isinstance(result["latency_seconds"], float)


def test_main_outputs_both_provider_results(monkeypatch, capsys):
    def fake_get_task(task: str):
        assert task == "response"
        return {
            "openai": lambda prompt: f"openai:{prompt}",
            "google": lambda prompt: f"google:{prompt}",
        }

    monkeypatch.setattr(compare_llm_responses, "_get_task", fake_get_task)
    monkeypatch.setattr(
        "sys.argv",
        [
            "compare_llm_responses.py",
            "--task",
            "response",
            "--prompt",
            "hello world",
        ],
    )

    compare_llm_responses.main()

    output = capsys.readouterr().out.strip()
    data = json.loads(output)

    assert data["task"] == "response"
    assert data["input_length"] == len("hello world")
    assert data["results"]["openai"]["ok"] is True
    assert data["results"]["google"]["ok"] is True
    assert data["results"]["openai"]["result"] == "openai:hello world"
    assert data["results"]["google"]["result"] == "google:hello world"
