"""Application settings and configuration management."""

from functools import lru_cache
from typing import Annotated
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "NER-LINK"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL / PostGIS
    POSTGRES_USER: str = "nerlink_user"
    POSTGRES_PASSWORD: str = "nerlink_secure_password"
    POSTGRES_DB: str = "nerlink"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 55432

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 56379
    REDIS_DB: int = 0

    # Study Corridor Configuration (Configurable geographic scope)
    CORRIDOR_NAME: str = "Guwahati-Tawang"
    CORRIDOR_MIN_LAT: float = 26.10
    CORRIDOR_MIN_LON: float = 91.50
    CORRIDOR_MAX_LAT: float = 27.70
    CORRIDOR_MAX_LON: float = 92.80

    # OSM Ingestion
    OSM_NETWORK_TYPE: str = "drive"
    OSM_DATA_DIR: str = "data/osm"

    # Evidence Storage & Incident Management (Phase 2)
    MEDIA_DIR: str = "data/evidence"
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]
    INCIDENT_ROAD_MATCH_RADIUS_M: float = 150.0  # Search radius in meters
    REDIS_STREAM_INCIDENTS: str = "events:incidents"
    REDIS_STREAM_ROADS: str = "events:roads"

    @field_validator("CORRIDOR_MIN_LAT", "CORRIDOR_MAX_LAT")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v

    @field_validator("CORRIDOR_MIN_LON", "CORRIDOR_MAX_LON")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v

    @property
    def database_url_sync(self) -> str:
        """Synchronous connection URL using psycopg for Alembic and CLI scripts."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_async(self) -> str:
        """Asynchronous connection URL using asyncpg for FastAPI application."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def corridor_bbox(self) -> tuple[float, float, float, float]:
        """Returns (south, west, north, east) bounding box tuple."""
        if self.CORRIDOR_MIN_LAT >= self.CORRIDOR_MAX_LAT:
            raise ValueError("CORRIDOR_MIN_LAT must be strictly less than CORRIDOR_MAX_LAT")
        if self.CORRIDOR_MIN_LON >= self.CORRIDOR_MAX_LON:
            raise ValueError("CORRIDOR_MIN_LON must be strictly less than CORRIDOR_MAX_LON")
        return (
            self.CORRIDOR_MIN_LAT,
            self.CORRIDOR_MIN_LON,
            self.CORRIDOR_MAX_LAT,
            self.CORRIDOR_MAX_LON,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
