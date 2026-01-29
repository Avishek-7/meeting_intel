import hashlib

def meeting_cache_key(transcript: str) -> str:
    transcript_hash = hashlib.sha256(
        transcript.encode("utf-8")
    ).hexdigest()

    return f"meeting:analysis:{transcript_hash}"