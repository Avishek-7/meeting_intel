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

    # Celery settings
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    class Config:
        # Load env from project root when running inside backend/
        env_file = "../.env"
        env_file_encoding = "utf-8"

settings = Settings()
