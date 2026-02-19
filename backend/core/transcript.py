import hashlib


def generate_transcript_hash(transcript: str) -> str:
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


def estimate_token_count(text: str) -> int:
    """Estimate token count using a conservative characters-per-token heuristic."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)
