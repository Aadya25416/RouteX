"""FastAPI endpoints for Meteorological Observations and Weather Pipeline."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.weather import (
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
) -> WeatherRefreshResponse:
    """
    Triggers an external meteorological ingestion run across corridor sampling waypoints.
    Persists normalized observations, updates Redis status, and notifies system subscribers.
    """
    service = WeatherService(session)
    return await service.refresh_corridor_weather(actor_id=current_user.id)


@router.get("/latest", response_model=list[WeatherObservationResponse])
async def get_latest_weather(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    min_lat: Annotated[float | None, Query()] = None,
    min_lon: Annotated[float | None, Query()] = None,
    max_lat: Annotated[float | None, Query()] = None,
    max_lon: Annotated[float | None, Query()] = None,
) -> list[WeatherObservationResponse]:
    """Retrieves the latest persisted meteorological readings with spatial filtering."""
    service = WeatherService(session)
    return await service.get_latest_observations(
        limit=limit,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )


@router.get("/status", response_model=WeatherStatusResponse)
async def get_weather_status(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WeatherStatusResponse:
    """
    Inspects weather pipeline operational health, observation freshness,
    last successful execution, and sampling point count.
    """
    service = WeatherService(session)
    return await service.get_status()
