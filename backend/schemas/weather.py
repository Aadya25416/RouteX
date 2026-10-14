"""Pydantic schemas for Weather Ingestion and Corridor Observations."""

import uuid
from datetime import datetime
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field


class WeatherObservationResponse(BaseModel):
    """Normalized meteorological observation or forecast reading."""
    id: uuid.UUID
    provider: str
    latitude: float
    longitude: float
    rainfall_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    snowfall_cm: float | None = None
    weather_code: int | None = None
    visibility_m: float | None = None
    temperature_c: float | None = None
    road_segment_id: str | None = None
    observed_at: datetime
    forecast_valid_at: datetime | None = None
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeatherStatusResponse(BaseModel):
    """Operational status, freshness, and ingestion metrics for weather feeds."""
    provider: str
    last_run_status: str
    last_successful_run: datetime | None = None
    last_error: str | None = None
    total_observations: int
    corridor_sample_points_count: int
    latest_observation_time: datetime | None = None
    is_stale: bool
    refresh_interval_minutes: int


class WeatherRefreshResponse(BaseModel):
    """Result summary of a weather refresh trigger."""
    provider: str
    sample_points_queried: int
    observations_persisted: int
    duration_seconds: float
    refreshed_at: datetime
