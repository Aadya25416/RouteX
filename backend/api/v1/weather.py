"""FastAPI endpoints for Meteorological Observations, Forecasts, and ML Feature Contracts."""

from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.weather import (
    WeatherForecastResponse,
    WeatherMLFeatureVector,
    WeatherObservationResponse,
    WeatherRefreshResponse,
    WeatherStatusResponse,
)
from backend.services.weather.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["Weather Ingestion"])


@router.post("/refresh", response_model=WeatherRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh_weather(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker"]))],
    forecast_days: Annotated[int, Query(ge=1, le=7, description="Number of forecast days to request")] = 2,
) -> WeatherRefreshResponse:
    """
    Triggers an external meteorological ingestion run across corridor sampling waypoints.
    Persists normalized current observations and hourly forecasts, updates Redis status, and notifies subscribers.
    """
    service = WeatherService(session)
    return await service.refresh_corridor_weather(actor_id=current_user.id, forecast_days=forecast_days)


@router.get("/latest", response_model=list[WeatherObservationResponse])
async def get_latest_weather(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    data_type: Annotated[str | None, Query(description="Filter by CURRENT, FORECAST, or OBSERVATION")] = None,
    road_segment_id: Annotated[str | None, Query(description="Filter by associated road segment ID")] = None,
    min_lat: Annotated[float | None, Query()] = None,
    min_lon: Annotated[float | None, Query()] = None,
    max_lat: Annotated[float | None, Query()] = None,
    max_lon: Annotated[float | None, Query()] = None,
) -> list[WeatherObservationResponse]:
    """Retrieves the latest persisted meteorological readings with spatial, data-type, and road-segment filtering."""
    service = WeatherService(session)
    return await service.get_latest_observations(
        limit=limit,
        data_type=data_type,
        road_segment_id=road_segment_id,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )


@router.get("/forecast", response_model=WeatherForecastResponse)
async def get_weather_forecast(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    latitude: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    longitude: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    road_segment_id: Annotated[str | None, Query()] = None,
    hours: Annotated[int, Query(ge=1, le=72, description="Forecast horizon in hours")] = 24,
) -> WeatherForecastResponse:
    """
    Retrieves hourly forecast prediction series and daily summaries for a requested coordinate
    or road segment along the study corridor.
    """
    service = WeatherService(session)
    return await service.get_forecast(
        latitude=latitude,
        longitude=longitude,
        road_segment_id=road_segment_id,
        hours=hours,
    )


@router.get("/features", response_model=WeatherMLFeatureVector)
async def get_weather_features_for_ml(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    latitude: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    longitude: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    road_segment_id: Annotated[str | None, Query()] = None,
    reference_time: Annotated[datetime | None, Query(description="Target reference timestamp in UTC")] = None,
) -> WeatherMLFeatureVector:
    """
    Supplies downstream machine learning pipelines with validated, feature-ready weather data:
    - Current surface conditions (temperature, humidity, wind, gusts, pressure, visibility, weather code, soil moisture)
    - Antecedent rolling rainfall accumulation windows (1h, 3h, 6h, 24h)
    - Future forecast rainfall accumulation windows (1h, 3h, 6h, 24h)
    - Provenance, explicit units, data freshness, and missingness indicators
    """
    service = WeatherService(session)
    return await service.get_weather_features_for_ml(
        latitude=latitude,
        longitude=longitude,
        road_segment_id=road_segment_id,
        reference_time=reference_time,
    )


@router.get("/status", response_model=WeatherStatusResponse)
async def get_weather_status(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WeatherStatusResponse:
    """
    Inspects weather pipeline operational health, observation freshness,
    last successful execution, total forecasts, and sampling point count.
    """
    service = WeatherService(session)
    return await service.get_status()
