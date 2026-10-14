"""FastAPI endpoints for Segment-level Traffic Observations and Aggregation."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.traffic import (
    TrafficAggregateRequest,
    TrafficAggregationSummary,
    TrafficObservationResponse,
)
from backend.services.traffic_service import TrafficService

router = APIRouter(prefix="/traffic", tags=["Traffic Ingestion"])


@router.get("", response_model=list[TrafficObservationResponse])
async def list_traffic_observations(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    road_segment_id: Annotated[str | None, Query(description="Filter by road segment ID")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TrafficObservationResponse]:
    """Retrieves recent traffic observations derived from vehicle GPS telemetry."""
    service = TrafficService(session)
    return await service.get_traffic_observations(
        road_segment_id=road_segment_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{road_segment_id}", response_model=TrafficObservationResponse)
async def get_segment_traffic(
    road_segment_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TrafficObservationResponse:
    """Retrieves latest traffic observation for a specific road segment."""
    service = TrafficService(session)
    items = await service.get_traffic_observations(road_segment_id=road_segment_id, limit=1)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No traffic observations recorded for road segment '{road_segment_id}'.",
        )
    return items[0]


@router.post("/aggregate", response_model=TrafficAggregationSummary, status_code=status.HTTP_200_OK)
async def aggregate_traffic(
    payload: TrafficAggregateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker"]))],
) -> TrafficAggregationSummary:
    """
    Triggers aggregation of vehicle GPS tracks over a sliding time window.
    Calculates speeds, congestion ratios, and data confidence levels.
    """
    service = TrafficService(session)
    return await service.calculate_traffic_conditions(
        window_minutes=payload.window_minutes,
        min_samples_for_high_confidence=payload.min_samples_for_high_confidence,
        actor_id=current_user.id,
    )
