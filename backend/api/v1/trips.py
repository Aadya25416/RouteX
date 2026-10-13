"""Trip lifecycle, vehicle assignment, and active rerouting endpoints."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.deliveries import _to_delivery_response
from backend.api.v1.vehicles import _to_vehicle_response
from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.logistics import Trip
from backend.models.users import User
from backend.schemas.logistics import (
    TripCancelRequest,
    TripCreateRequest,
    TripListResponse,
    TripPauseRequest,
    TripResponse,
    TripUpdateRequest,
)
from backend.schemas.routing import RerouteResponse
from backend.services.logistics_service import LogisticsService

router = APIRouter(prefix="/trips", tags=["Trips"])


async def _to_trip_response(trip: Trip, session: AsyncSession) -> TripResponse:
    veh_resp = _to_vehicle_response(trip.vehicle) if trip.vehicle else None
    deliv_resp = await _to_delivery_response(trip.delivery, session) if trip.delivery else None

    return TripResponse(
        id=trip.id,
        vehicle_id=trip.vehicle_id,
        delivery_id=trip.delivery_id,
        driver_id=trip.driver_id,
        current_route_id=trip.current_route_id,
        status=trip.status,
        estimated_duration_s=trip.estimated_duration_s,
        estimated_distance_m=trip.estimated_distance_m,
        started_at=trip.started_at,
        paused_at=trip.paused_at,
        completed_at=trip.completed_at,
        cancellation_reason=trip.cancellation_reason,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
        vehicle=veh_resp,
        delivery=deliv_resp,
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> TripResponse:
    """
    Creates and assigns a trip connecting a delivery to a vehicle.
    Plans initial route and updates vehicle and delivery statuses atomically.
    """
    service = LogisticsService(session)
    trip = await service.create_and_assign_trip(
        vehicle_id=payload.vehicle_id,
        delivery_id=payload.delivery_id,
        driver_id=payload.driver_id,
        routing_mode=payload.routing_mode,
        require_verified_safe=payload.require_verified_safe,
        actor_id=current_user.id,
    )
    full_trip = await service.get_trip(trip.id)
    return await _to_trip_response(full_trip, session)


@router.get("", response_model=TripListResponse)
async def list_trips(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[str | None, Query(description="Filter by trip status")] = None,
    vehicle_id: Annotated[uuid.UUID | None, Query(description="Filter by vehicle")] = None,
    delivery_id: Annotated[uuid.UUID | None, Query(description="Filter by delivery")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TripListResponse:
    """Lists trips with optional filters."""
    service = LogisticsService(session)
    total, items = await service.list_trips(
        status_filter=status,
        vehicle_id=vehicle_id,
        delivery_id=delivery_id,
        limit=limit,
        offset=offset,
    )
    res_items = []
    for t in items:
        res_items.append(await _to_trip_response(t, session))
    return TripListResponse(total=total, items=res_items)


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TripResponse:
    """Retrieves full trip details including vehicle, delivery, and current route."""
    service = LogisticsService(session)
    trip = await service.get_trip(trip_id)
    return await _to_trip_response(trip, session)


@router.post("/{trip_id}/start", response_model=TripResponse)
async def start_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin"]))],
) -> TripResponse:
    """Starts a planned trip (PLANNED -> IN_TRANSIT), updating vehicle and delivery."""
    service = LogisticsService(session)
    await service.start_trip(trip_id, actor_id=current_user.id)
    full_trip = await service.get_trip(trip_id)
    return await _to_trip_response(full_trip, session)


@router.post("/{trip_id}/pause", response_model=TripResponse)
async def pause_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin"]))],
    payload: TripPauseRequest | None = None,
) -> TripResponse:
    """Pauses an in-transit trip (IN_TRANSIT -> PAUSED)."""
    service = LogisticsService(session)
    reason = payload.reason if payload else None
    await service.pause_trip(trip_id, reason=reason, actor_id=current_user.id)
    full_trip = await service.get_trip(trip_id)
    return await _to_trip_response(full_trip, session)


@router.post("/{trip_id}/resume", response_model=TripResponse)
async def resume_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin"]))],
) -> TripResponse:
    """Resumes a paused trip (PAUSED -> IN_TRANSIT)."""
    service = LogisticsService(session)
    await service.resume_trip(trip_id, actor_id=current_user.id)
    full_trip = await service.get_trip(trip_id)
    return await _to_trip_response(full_trip, session)


@router.post("/{trip_id}/complete", response_model=TripResponse)
async def complete_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin"]))],
) -> TripResponse:
    """Completes a trip, releases vehicle to AVAILABLE, and marks delivery DELIVERED."""
    service = LogisticsService(session)
    await service.complete_trip(trip_id, actor_id=current_user.id)
    full_trip = await service.get_trip(trip_id)
    return await _to_trip_response(full_trip, session)


@router.post("/{trip_id}/cancel", response_model=TripResponse)
async def cancel_trip(
    trip_id: uuid.UUID,
    payload: TripCancelRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> TripResponse:
    """Cancels a trip, releases vehicle to AVAILABLE, and resets delivery to PENDING."""
    service = LogisticsService(session)
    await service.cancel_trip(trip_id, cancellation_reason=payload.cancellation_reason, actor_id=current_user.id)
    full_trip = await service.get_trip(trip_id)
    return await _to_trip_response(full_trip, session)


@router.post("/{trip_id}/reroute", response_model=RerouteResponse)
async def reroute_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> RerouteResponse:
    """
    Evaluates current road conditions against the trip's route and computes an alternative.
    Returns new route or NO_SAFE_ROUTE if no viable alternative exists.
    """
    service = LogisticsService(session)
    return await service.reroute_trip(trip_id=trip_id, actor_id=current_user.id)
