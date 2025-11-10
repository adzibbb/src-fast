# core/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"  # production, staging, development

    # Database
    DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # JWT Claims
    JWT_ISSUER: str = "stress-relief-chatter"
    JWT_AUDIENCE: str = "stress-relief-chatter-users"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Allowed hosts
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # Password policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_NON_ALPHANUMERIC: bool = True
    PASSWORD_REQUIRE_UNIQUE_CHARS: int = 4

    # Database logging
    SQL_ECHO: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()