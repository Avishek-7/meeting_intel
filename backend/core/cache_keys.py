import hashlib

def meeting_cache_key(transcript: str) -> str:
    """Generate a cache key for meeting analysis results.
    Args:
        transcript: The meeting transcript text.
    
    Returns:
        A cache key in the format 'meeting:analysis:{sha256_hash}'.
    
    Raise:
        ValueError: If transcript is empty.
    """
    if not transcript:
        raise ValueError("Transcript cannot be empty.")
    
    transcript_hash = hashlib.sha256(
        transcript.encode("utf-8")
    ).hexdigest()

    return f"meeting:analysis:{transcript_hash}"