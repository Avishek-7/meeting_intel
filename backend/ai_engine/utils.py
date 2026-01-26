import hashlib

def hash_text(text: str) -> str:
    """Generate a SHA256 hash of the given text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def word_count(text: str) -> int:
    """Count the number of words in the given text."""
    return len(text.split())