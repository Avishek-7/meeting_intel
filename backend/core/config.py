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
    celery_result_bakcend: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
