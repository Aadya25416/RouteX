"""Pydantic schemas for Weather Ingestion, Forecast Horizons, and ML Data Contracts."""

from datetime import datetime
from typing import Annotated, Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class WeatherObservationResponse(BaseModel):
    """Normalized meteorological observation, current condition, or forecast reading."""
    id: uuid.UUID
    provider: str
    data_type: str = "CURRENT"
    latitude: float
    longitude: float
    rainfall_mm: float | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    showers_mm: float | None = None
    precipitation_probability_pct: float | None = None
    relative_humidity_pct: float | None = None
    dew_point_c: float | None = None
    apparent_temperature_c: float | None = None
    pressure_msl_hpa: float | None = None
    surface_pressure_hpa: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    wind_gusts_kmh: float | None = None
    snowfall_cm: float | None = None
    weather_code: int | None = None
    visibility_m: float | None = None
    temperature_c: float | None = None
    cloud_cover_pct: float | None = None
    et0_evapotranspiration_mm: float | None = None
    soil_moisture_m3m3: float | None = None
    road_segment_id: str | None = None
    observed_at: datetime
    forecast_valid_at: datetime | None = None
    issue_time: datetime | None = None
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeatherStatusResponse(BaseModel):
    """Operational status, freshness, and ingestion metrics for weather feeds."""
    provider: str
    last_run_status: str
    last_successful_run: datetime | None = None
    last_error: str | None = None
    total_observations: int
    total_current_observations: int = 0
    total_forecast_records: int = 0
    corridor_sample_points_count: int
    latest_observation_time: datetime | None = None
    is_stale: bool
    refresh_interval_minutes: int


class WeatherRefreshResponse(BaseModel):
    """Result summary of a weather refresh trigger."""
    provider: str
    sample_points_queried: int
    observations_persisted: int
    current_observations_persisted: int = 0
    forecast_records_persisted: int = 0
    duration_seconds: float
    refreshed_at: datetime


class HourlyForecastItem(BaseModel):
    """Hourly forecast prediction entry."""
    valid_time: datetime
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    precipitation_mm: float | None = None
    rain_mm: float | None = None
    showers_mm: float | None = None
    snowfall_cm: float | None = None
    precipitation_probability_pct: float | None = None
    relative_humidity_pct: float | None = None
    dew_point_c: float | None = None
    pressure_msl_hpa: float | None = None
    surface_pressure_hpa: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    wind_gusts_kmh: float | None = None
    visibility_m: float | None = None
    weather_code: int | None = None
    cloud_cover_pct: float | None = None
    soil_moisture_m3m3: float | None = None
    et0_evapotranspiration_mm: float | None = None


class DailyForecastSummary(BaseModel):
    """Daily aggregated meteorological metrics."""
    date: str
    weather_code: int | None = None
    temperature_2m_max_c: float | None = None
    temperature_2m_min_c: float | None = None
    apparent_temperature_max_c: float | None = None
    apparent_temperature_min_c: float | None = None
    precipitation_sum_mm: float | None = None
    rain_sum_mm: float | None = None
    showers_sum_mm: float | None = None
    snowfall_sum_cm: float | None = None
    precipitation_probability_max_pct: float | None = None
    wind_speed_10m_max_kmh: float | None = None
    wind_gusts_10m_max_kmh: float | None = None
    sunrise: str | None = None
    sunset: str | None = None


class WeatherForecastResponse(BaseModel):
    """Forecast timeseries and daily summary response for corridor points."""
    provider: str
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    generated_at: datetime
    horizon_hours: int
    hourly: list[HourlyForecastItem]
    daily: list[DailyForecastSummary] = Field(default_factory=list)


class WeatherConditionFeatures(BaseModel):
    """Current instantaneous surface weather conditions."""
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    dew_point_c: float | None = None
    precipitation_mm: float | None = None
    rainfall_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    wind_direction_deg: float | None = None
    visibility_m: float | None = None
    pressure_msl_hpa: float | None = None
    surface_pressure_hpa: float | None = None
    weather_code: int | None = None
    cloud_cover_pct: float | None = None
    soil_moisture_m3m3: float | None = None
    et0_evapotranspiration_mm: float | None = None


class WeatherMLFeatureVector(BaseModel):
    """Downstream machine-learning-ready meteorological feature contract."""
    schema_version: str = "1.0"
    provider: str = "open-meteo"
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    road_segment_distance_m: float | None = None
    spatial_match_confidence: str = "UNMATCHED"  # HIGH, MEDIUM, LOW, UNMATCHED
    reference_time: datetime
    issue_time: datetime | None = None
    data_freshness_seconds: float | None = None
    is_stale: bool = False
    current_conditions: WeatherConditionFeatures
    rainfall_accumulation_past: dict[str, float | None]
    past_data_completeness: dict[str, str]
    rainfall_forecast_accumulation: dict[str, float | None]
    forecast_data_completeness: dict[str, str]
    units: dict[str, str]
    missing_indicators: list[str]
