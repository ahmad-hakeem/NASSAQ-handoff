"""
NASSAQ Production Configuration
Centralized config from environment variables with validation.

DEPLOYMENT SAFETY POLICY (PERMANENT & NON-NEGOTIABLE):
- Production data must NEVER be lost, overwritten, or replaced
- Seed/demo data must NEVER be injected into production
- Destructive migrations are BLOCKED in production
- Environment separation is strictly enforced
"""
import os
from typing import Optional


SEED_BLOCKED_ENVIRONMENTS = {"production", "staging"}

SAFE_MIGRATION_OPS = {"add_field", "add_collection", "add_index", "create_index"}
DESTRUCTIVE_MIGRATION_OPS = {"drop", "delete", "rename", "remove", "truncate", "replace"}


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
    def is_staging(cls) -> bool:
        return cls.ENVIRONMENT == "staging"

    @classmethod
    def is_development(cls) -> bool:
        return cls.ENVIRONMENT in ("development", "dev", "")

    @classmethod
    def seed_allowed(cls) -> bool:
        return cls.ENVIRONMENT not in SEED_BLOCKED_ENVIRONMENTS

    @classmethod
    def destructive_ops_allowed(cls) -> bool:
        return cls.is_development()

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
            raise ValueError("CORS_ORIGINS must be explicitly set in production (wildcard '*' is not allowed)")
        if cls.is_production() and cls.DEBUG:
            issues.append("DEBUG should be false in production")
        if cls.is_production() and cls.DB_NAME == "test_database":
            issues.append("DB_NAME is 'test_database' in production — use a production database name")
        return issues

    @classmethod
    def deployment_checklist(cls) -> dict:
        checks = {
            "environment_set": cls.ENVIRONMENT != "",
            "environment_value": cls.ENVIRONMENT,
            "database_name": cls.DB_NAME,
            "database_is_production_safe": cls.DB_NAME != "test_database" if cls.is_production() else True,
            "seed_blocked": not cls.seed_allowed() if cls.is_production() else "n/a",
            "destructive_ops_blocked": not cls.destructive_ops_allowed() if cls.is_production() else "n/a",
            "jwt_secret_set": bool(cls.JWT_SECRET),
            "cors_configured": cls.CORS_ORIGINS != ["*"] if cls.is_production() else True,
            "debug_off": not cls.DEBUG if cls.is_production() else True,
        }
        all_passed = all(
            v is True or v == "n/a" or (isinstance(v, str) and v)
            for k, v in checks.items()
        )
        checks["all_passed"] = all_passed
        return checks


config = NassaqConfig()
