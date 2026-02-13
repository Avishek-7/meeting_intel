from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    app_name: str = "MeetingIntel"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    # Auth cookie settings
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_DOMAIN: Optional[str] = None
    AUTH_COOKIE_PATH: str = "/"
    
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

    # Redis settings
    redis_url: Optional[str] = None
    redis_socket_timeout: float = 5
    redis_socket_connect_timeout: float = 5

    # Security/Privacy settings
    PII_HASH_PEPPER: str = ""  # Should be set in production via environment variable

    class Config:
        # Load env from project root when running inside backend/
        env_file = str(Path(__file__).resolve().parent.parent.parent / ".env")
        env_file_encoding = "utf-8"

    @field_validator("PII_HASH_PEPPER")
    @classmethod
    def validate_pii_hash_pepper(cls, v: str) -> str:
        """
        Validate PII_HASH_PEPPER is set.
        
        An empty pepper provides no additional hash protection.
        This validator warns if the pepper is empty, to prevent
        silent security degradation in production.
        """
        if not v or not v.strip():
            is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
            
            if is_production:
                # In production, log as critical error
                logger.critical(
                    "PII_HASH_PEPPER is empty in production. "
                    "PII hashes are vulnerable to enumeration attacks. "
                    "Set PII_HASH_PEPPER environment variable immediately."
                )
            else:
                # In development, log as warning
                logger.warning(
                    "PII_HASH_PEPPER is not set. "
                    "Hashed identifiers are vulnerable to enumeration attacks. "
                    "Set this environment variable in production."
                )
        
        return v

settings = Settings()
