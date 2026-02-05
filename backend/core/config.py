from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "MeetingIntel"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    
    # Database settings
    DATABASE_URL: str

    # OpenAI settings
    OPENAI_API_KEY: str

    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_FALLBACK_MODEL: str = "gpt-3.5-turbo"

    OPENAI_TEMPERATURE: float = 0.3
    OPENAI_REQUEST_TIMEOUT: int = 30  # seconds
    OPENAI_MAX_TOKENS_PER_REQUEST: int = 2000
    
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_RETRY_BASE_WAIT: int = 2  # seconds

    # Celery settings
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    class Config:
        # Load env from project root when running inside backend/
        env_file = str(Path(__file__).resolve().parent.parent.parent / ".env")
        env_file_encoding = "utf-8"

settings = Settings()
