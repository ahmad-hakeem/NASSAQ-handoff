"""
NASSAQ Production Configuration
Centralized config from environment variables with validation.
"""
import os
from typing import Optional


class NassaqConfig:
    MONGO_URL: str = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.environ.get("DB_NAME", "test_database")
    JWT_SECRET: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    CORS_ORIGINS: list = os.environ.get("CORS_ORIGINS", "*").split(",")
    ALLOWED_HOSTS: list = os.environ.get("ALLOWED_HOSTS", "*").split(",")

    RATE_LIMIT_LOGIN: int = int(os.environ.get("RATE_LIMIT_LOGIN", "10"))
    RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    VERSION: str = "3.0.0"
    APP_NAME: str = "NASSAQ - نَسَّق"

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENVIRONMENT == "production"

    @classmethod
    def validate(cls) -> list:
        issues = []
        if not cls.JWT_SECRET:
            if cls.is_production():
                raise ValueError("JWT_SECRET_KEY must be set in production environment")
            issues.append("JWT_SECRET not set")
        if cls.is_production() and cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET_KEY too short for production (min 32 chars)")
        if cls.is_production() and cls.CORS_ORIGINS == ["*"]:
            issues.append("CORS_ORIGINS should not be '*' in production")
        if cls.is_production() and cls.DEBUG:
            issues.append("DEBUG should be false in production")
        return issues


config = NassaqConfig()
