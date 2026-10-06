from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Central application configuration.

    Values are loaded from environment variables and, for local
    development, an optional .env file.

    Environment variables take precedence over .env values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Sovereign Asset Ledger"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./sal.db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_POOL_PRE_PING: bool = True

    # Authentication
    SECRET_KEY: str = Field(
        default="development-only-change-this-secret",
        repr=False,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Evidence storage
    SAL_EVIDENCE_STORAGE_ROOT: str = str(
        PROJECT_ROOT / "storage" / "evidence"
    )

    @model_validator(mode="after")
    def validate_secret_key(self):
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == "development-only-change-this-secret":
                raise ValueError(
                    "SECRET_KEY must be explicitly configured for production"
                )

            if not self.DATABASE_URL.startswith(("postgresql://", "postgresql+")):
                raise ValueError(
                    "DATABASE_URL must use PostgreSQL in production"
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings instance.
    """
    return Settings()


settings = get_settings()
