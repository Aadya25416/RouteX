"""Tests for settings and environment configuration validation."""

import pytest
from pydantic import ValidationError
from backend.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.APP_NAME == "NER-LINK"
    assert settings.POSTGRES_PORT == 55432
    assert settings.REDIS_PORT == 56379
    assert "postgresql+psycopg://" in settings.database_url_sync
    assert "postgresql+asyncpg://" in settings.database_url_async
    assert "redis://" in settings.redis_url


def test_valid_corridor_bbox():
    settings = Settings(
        CORRIDOR_MIN_LAT=26.0,
        CORRIDOR_MIN_LON=91.0,
        CORRIDOR_MAX_LAT=27.5,
        CORRIDOR_MAX_LON=92.5,
    )
    bbox = settings.corridor_bbox
    assert bbox == (26.0, 91.0, 27.5, 92.5)


def test_invalid_latitude():
    with pytest.raises(ValidationError):
        Settings(CORRIDOR_MIN_LAT=95.0)

    with pytest.raises(ValidationError):
        Settings(CORRIDOR_MAX_LAT=-95.0)


def test_invalid_longitude():
    with pytest.raises(ValidationError):
        Settings(CORRIDOR_MIN_LON=-190.0)

    with pytest.raises(ValidationError):
        Settings(CORRIDOR_MAX_LON=190.0)


def test_inverted_bbox_raises_error():
    settings = Settings(
        CORRIDOR_MIN_LAT=28.0,
        CORRIDOR_MAX_LAT=26.0,
    )
    with pytest.raises(ValueError, match="strictly less than"):
        _ = settings.corridor_bbox


def test_cors_origins_parsing():
    # Comma-separated string
    s1 = Settings(CORS_ORIGINS="http://localhost:3000, https://routex.ai")
    assert s1.CORS_ORIGINS == ["http://localhost:3000", "https://routex.ai"]

    # JSON array string
    s2 = Settings(CORS_ORIGINS='["http://localhost:3000", "https://app.routex.ai"]')
    assert s2.CORS_ORIGINS == ["http://localhost:3000", "https://app.routex.ai"]

    # Python list
    s3 = Settings(CORS_ORIGINS=["http://localhost:3000", "https://app.routex.ai"])
    assert s3.CORS_ORIGINS == ["http://localhost:3000", "https://app.routex.ai"]


def test_production_cors_wildcard_rejected():
    with pytest.raises(ValidationError, match=r"Wildcard '\*' CORS_ORIGINS is prohibited"):
        Settings(
            APP_ENV="production",
            CORS_ORIGINS="*",
            JWT_SECRET_KEY="a" * 32,
            ALLOW_DEV_AUTH_HEADERS=False,
            POSTGRES_PASSWORD="a_very_strong_production_password_2026",
        )


def test_production_weak_postgres_password_rejected():
    with pytest.raises(ValidationError, match="strong, explicit POSTGRES_PASSWORD"):
        Settings(
            APP_ENV="production",
            POSTGRES_PASSWORD="nerlink_secure_password",
            JWT_SECRET_KEY="a" * 32,
            ALLOW_DEV_AUTH_HEADERS=False,
            CORS_ORIGINS="https://routex.ai",
        )


def test_production_dev_auth_headers_rejected():
    with pytest.raises(ValidationError, match="ALLOW_DEV_AUTH_HEADERS cannot be True"):
        Settings(
            APP_ENV="production",
            ALLOW_DEV_AUTH_HEADERS=True,
            JWT_SECRET_KEY="a" * 32,
            POSTGRES_PASSWORD="a_very_strong_production_password_2026",
            CORS_ORIGINS="https://routex.ai",
        )


def test_production_weak_jwt_secret_rejected():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="too_short",
            ALLOW_DEV_AUTH_HEADERS=False,
            POSTGRES_PASSWORD="a_very_strong_production_password_2026",
            CORS_ORIGINS="https://routex.ai",
        )


def test_production_valid_configuration():
    valid = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="super_strong_production_random_secret_32_chars!",
        POSTGRES_PASSWORD="strong_random_db_password_never_default",
        ALLOW_DEV_AUTH_HEADERS=False,
        CORS_ORIGINS="https://routex.ai, https://app.routex.ai",
    )
    assert valid.APP_ENV == "production"
    assert valid.CORS_ORIGINS == ["https://routex.ai", "https://app.routex.ai"]
    assert valid.ALLOW_DEV_AUTH_HEADERS is False

