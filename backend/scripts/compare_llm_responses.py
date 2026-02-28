import argparse
import json
import time
from typing import Any, Callable


def _run_provider_call(
    provider_name: str,
    fn: Callable[[str], Any],
    payload: str,
) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        result = fn(payload)
        latency = time.perf_counter() - start
        return {
            "provider": provider_name,
            "ok": True,
            "latency_seconds": round(latency, 3),
            "result": result,
            "error": None,
        }
    except Exception as exc:
        latency = time.perf_counter() - start
        return {
            "provider": provider_name,
            "ok": False,
            "latency_seconds": round(latency, 3),
            "result": None,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def _get_task(task: str) -> dict[str, Callable[[str], Any]]:
    from ai_engine import google_llm, llm

    if task == "response":
        return {
            "openai": llm.generate_response,
            "google": google_llm.generate_response,
        }
    if task == "summary":
        return {
            "openai": llm.summarize_text,
            "google": google_llm.summarize_text,
        }
    return {
        "openai": llm.extract_action_items,
        "google": google_llm.extract_action_items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare OpenAI and Google LLM outputs for the same input.",
    )
    parser.add_argument(
        "--task",
        choices=["response", "summary", "action_items"],
        default="response",
        help="Which function to test on both providers.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Input prompt/transcript passed to both providers.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )

    args = parser.parse_args()

    task_map = _get_task(args.task)
    results = {
        provider: _run_provider_call(provider, fn, args.prompt)
        for provider, fn in task_map.items()
    }

    output = {
        "task": args.task,
        "input_length": len(args.prompt),
        "results": results,
    }

    if args.pretty:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
