"""Application settings and configuration management."""

from functools import lru_cache
from typing import Annotated
from pydantic import AliasChoices, Field, field_validator
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

    # Evidence Storage & Incident Management (Data Collection)
    MEDIA_DIR: str = "data/evidence"
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    ALLOWED_IMAGE_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/tiff",
        "image/geotiff",
    ]
    INCIDENT_ROAD_MATCH_RADIUS_M: float = 150.0  # Search radius in meters
    REDIS_STREAM_INCIDENTS: str = "events:incidents"
    REDIS_STREAM_ROADS: str = "events:roads"
    REDIS_STREAM_EVIDENCE: str = "events:evidence"

    # Weather Ingestion (Open-Meteo)
    OPEN_METEO_API_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_REQUEST_TIMEOUT_SECONDS: float = 10.0
    WEATHER_REFRESH_INTERVAL_MINUTES: int = 60
    WEATHER_SAMPLE_GRID_STEP_DEG: float = 0.5
    WEATHER_FORECAST_DAYS: int = 3
    WEATHER_MAX_RETRIES: int = 3
    WEATHER_RETRY_BACKOFF_SECONDS: float = 0.5
    WEATHER_STALE_THRESHOLD_MINUTES: int = 120

    # GPS & Telemetry Ingestion
    GPS_SNAP_THRESHOLD_M: float = 100.0
    GPS_MAX_SPEED_KMH: float = 250.0
    GPS_BATCH_MAX_SIZE: int = 200

    # ML Processing Contract
    ML_CLAIM_TIMEOUT_MINUTES: int = 15
    ML_SERVICE_ROLE: str = "ml_service"

    # Satellite Ingestion Adapter
    SATELLITE_PROVIDER: str = "copernicus_sentinel2"
    SATELLITE_MAX_CLOUD_COVER_PERCENT: float = 40.0

    # Authentication & JWT Security
    JWT_SECRET_KEY: str = "nerlink-super-secret-jwt-key-change-in-prod-1234567890"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOW_DEV_AUTH_HEADERS: bool = True

    # Refresh Cookie Settings
    REFRESH_COOKIE_NAME: str = "rx_refresh_token"
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_HTTPONLY: bool = True
    REFRESH_COOKIE_SAMESITE: str = "lax"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"

    # Login Rate Limiting (Redis-backed)
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 300
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # CORS Origins
    CORS_ORIGINS: list[str] | str = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Admin Provisioning Configuration (supports ADMIN_EMAIL / ADMIN_PASSWORD or ADMIN_BOOTSTRAP_*)
    ADMIN_BOOTSTRAP_EMAIL: str = Field(
        default="admin@routex.ai",
        validation_alias=AliasChoices("ADMIN_BOOTSTRAP_EMAIL", "ADMIN_EMAIL"),
    )
    ADMIN_BOOTSTRAP_NAME: str = Field(
        default="RouteX Administrator",
        validation_alias=AliasChoices("ADMIN_BOOTSTRAP_NAME", "ADMIN_NAME"),
    )
    ADMIN_BOOTSTRAP_PASSWORD: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_BOOTSTRAP_PASSWORD", "ADMIN_PASSWORD"),
    )

    @property
    def ADMIN_EMAIL(self) -> str:
        return self.ADMIN_BOOTSTRAP_EMAIL

    @property
    def ADMIN_PASSWORD(self) -> str | None:
        return self.ADMIN_BOOTSTRAP_PASSWORD

    @property
    def ADMIN_NAME(self) -> str:
        return self.ADMIN_BOOTSTRAP_NAME

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return []

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: list[str], info) -> list[str]:
        app_env = info.data.get("APP_ENV", "development") if info.data else "development"
        if app_env == "production":
            if not v:
                raise ValueError("Production environment requires explicit CORS_ORIGINS.")
            if "*" in v:
                raise ValueError(
                    "Wildcard '*' CORS_ORIGINS is prohibited in production when credentials are enabled."
                )
        return v

    @field_validator("POSTGRES_PASSWORD")
    @classmethod
    def validate_postgres_password(cls, v: str, info) -> str:
        app_env = info.data.get("APP_ENV", "development") if info.data else "development"
        if app_env == "production" and (
            not v or "nerlink_secure_password" in v or len(v) < 8
        ):
            raise ValueError(
                "Production environment requires a strong, explicit POSTGRES_PASSWORD."
            )
        return v

    @field_validator("ALLOW_DEV_AUTH_HEADERS")
    @classmethod
    def validate_dev_auth_headers(cls, v: bool, info) -> bool:
        app_env = info.data.get("APP_ENV", "development") if info.data else "development"
        if app_env == "production" and v is True:
            raise ValueError(
                "ALLOW_DEV_AUTH_HEADERS cannot be True in production environment."
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        app_env = info.data.get("APP_ENV", "development") if info.data else "development"
        if app_env == "production" and (
            not v or "change-in-prod" in v or "nerlink_super_secret" in v or len(v) < 32
        ):
            raise ValueError(
                "Production environment requires a strong, explicit JWT_SECRET_KEY of at least 32 characters."
            )
        return v

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


settings = get_settings()
