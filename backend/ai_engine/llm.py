from openai import OpenAI
from core.config import settings
from ai_engine.prompts.loader import load_prompt
import logging

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a precise, reliable AI assistant specialized in "
    "analyzing meeting transcripts."
)

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 0.3

def generate_response(prompt: str) -> str:
    """
    Sends a prompt to OpenAI and returns the raw text response.

    This function is intentionally thin:
    - No business logic
    - No parsing
    - No orchestration 
    """

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=DEFAULT_TEMPERATURE,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from LLM")
        
        return content.strip()
    
    except Exception as e:
        logging.error("OpenAI LLM call failed: %s", e)
        raise RuntimeError("Failed to generate LLM response") from e
    

def summarize_text(text: str, version: str = "v1") -> str:
    """
    Generates a concise meeting summary using a versioned prompt. 
    """
    prompt_template = load_prompt(f"summary_{version}")
    prompt = prompt_template.replace("{{text}}", text)
    
    return generate_response(prompt)


def extract_action_items(text: str, version: str = "v1") -> list[str]:
    """
    Extracts action items from a meeting transcript.

    Returns a list of strings.
    Parsing is intentionally convservation and defensive.
    """
    prompt_template = load_prompt(f"action_items_{version}")
    prompt = prompt_template.replace("{{text}}", text)

    response = generate_response(prompt)

    # Defensive parsing: strip bullets and ignore empty lines
    items=[]
    for line in response.splitlines():
        cleaned = line.lstrip("-•* ").strip()
        if cleaned:
            items.append(cleaned)

    return items