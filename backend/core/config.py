from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, ValidationInfo
from typing import Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    app_name: str = "MeetingIntel"
    ENVIRONMENT: str = "development"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    # Auth cookie settings
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: Optional[bool] = None
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
    MAX_TRANSCRIPT_TOKENS: int = 12000
    
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_RETRY_BASE_WAIT: int = 2  # seconds

    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_MODEL: str = "gemini-2.5-pro"
    GOOGLE_FALLBACK_MODEL: str = "gemini-2.5-flash"

    GOOGLE_API_TIMEOUT_SECONDS: int = 30
    GOOGLE_TEMPERATURE: float = 0.3
    GOOGLE_MAX_TOKENS_PER_REQUEST: int = 2000
    GOOGLE_MAX_RETRIES: int = 3
    GOOGLE_RETRY_BASE_WAIT: int = 2  # seconds


    # Cache tuning
    MEETING_CACHE_TTL_SECONDS: int = 600

    # Rate limiting and abuse protection
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 60
    RATE_LIMIT_MAX_REQUESTS_ANON: int = 30

    # Daily caps (set to None to disable)
    DAILY_TOKEN_CAP: Optional[int] = 30000
    DAILY_COST_CAP_USD: Optional[Decimal] = 3.00

    # Celery settings
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    # Redis settings
    redis_url: Optional[str] = None
    redis_socket_timeout: float = 5
    redis_socket_connect_timeout: float = 5

    # CORS — comma-separated list of allowed frontend origins
    # Include common local frontend dev ports by default.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Security/Privacy settings
    PII_HASH_PEPPER: str = ""  # Should be set in production via environment variable

    # Stripe billing (optional — billing endpoints 503 if not set)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_PRICE_ID: Optional[str] = None
    STRIPE_ENTERPRISE_PRICE_ID: Optional[str] = None
    BILLING_ALLOWED_REDIRECT_HOSTS: str = "localhost,127.0.0.1"

    # Sentry (optional)
    SENTRY_DSN: Optional[str] = None

    # Load env from project root when running inside backend/
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
    )

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long.")
        return v

    @field_validator("AUTH_COOKIE_SECURE", mode="before")
    @classmethod
    def default_auth_cookie_secure(cls, v, info: ValidationInfo):
        if v is not None:
            return v
        environment = (
            info.data.get("ENVIRONMENT")
            if info.data.get("ENVIRONMENT") is not None
            else getattr(cls, "ENVIRONMENT", "development")
        ).lower()
        return environment not in {"development", "local", "test"}

    @field_validator("PII_HASH_PEPPER")
    @classmethod
    def validate_pii_hash_pepper(cls, v: str, info: ValidationInfo) -> str:
        """
        Validate PII_HASH_PEPPER is set.
        
        An empty pepper provides no additional hash protection.
        This validator warns if the pepper is empty, to prevent
        silent security degradation in production.
        """
        if not v or not v.strip():
            environment = (info.data.get("ENVIRONMENT") or "").lower()
            is_production = environment == "production"
            
            if is_production:
                # In production, log as critical error and fail fast
                logger.critical(
                    "PII_HASH_PEPPER is empty in production. "
                    "PII hashes are vulnerable to enumeration attacks. "
                    "Set PII_HASH_PEPPER environment variable immediately."
                )
                raise ValueError(
                    "PII_HASH_PEPPER must be set in production to prevent enumeration attacks."
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
