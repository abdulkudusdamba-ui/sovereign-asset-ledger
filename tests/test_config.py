import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_environment_allows_default_secret():
    settings = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="development-only-change-this-secret",
    )

    assert settings.ENVIRONMENT == "development"
    assert settings.SECRET_KEY == "development-only-change-this-secret"


def test_production_environment_rejects_default_secret():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="development-only-change-this-secret",
        )


def test_production_environment_accepts_real_secret():
    strong_secret = "a" * 64

    settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=strong_secret,
    )

    assert settings.ENVIRONMENT == "production"
    assert settings.SECRET_KEY == strong_secret


def test_non_production_environment_accepts_explicit_secret():
    settings = Settings(
        ENVIRONMENT="staging",
        SECRET_KEY="staging-secret-for-tests-only",
    )

    assert settings.ENVIRONMENT == "staging"
    assert settings.SECRET_KEY == "staging-secret-for-tests-only"


def test_database_pool_defaults():
    settings = Settings()

    assert settings.DATABASE_POOL_SIZE == 5
    assert settings.DATABASE_MAX_OVERFLOW == 10
    assert settings.DATABASE_POOL_TIMEOUT == 30
    assert settings.DATABASE_POOL_RECYCLE == 1800
    assert settings.DATABASE_POOL_PRE_PING is True
