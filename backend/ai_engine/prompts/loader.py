from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

def load_prompt(prompt_name: str) -> str:
    path = PROMPTS_DIR / f"{prompt_name}.txt"
    return path.read_text(encoding="utf-8")