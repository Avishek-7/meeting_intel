from ai_engine.preprocess import clean_text, chunk_text

def test_clean_text_strips_whitespace():
    text = "  hello world  "
    assert clean_text(text) == "hello world"

def test_chunk_text_splits_correctly():
    # Test with words separated by spaces
    text = " ".join(["word"] * 2500)  # 2500 words
    chunks = chunk_text(text, chunk_size=1000)

    assert len(chunks) == 3  # 2500 words / 1000 = 2.5, so 3 chunks
    assert len(chunks[0].split()) == 1000  # First chunk has 1000 words