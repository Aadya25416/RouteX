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
