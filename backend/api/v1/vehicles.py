"""Vehicle fleet management and GPS location ingestion endpoints."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.logistics import VehicleLocation
from backend.models.users import User
from backend.schemas.logistics import (
    LatestVehicleLocationResponse,
    MultiVehicleTelemetryBatchRequest,
    VehicleCreateRequest,
    VehicleListResponse,
    VehicleLocationBatchCreateRequest,
    VehicleLocationBatchResponse,
    VehicleLocationCreateRequest,
    VehicleLocationListResponse,
    VehicleLocationResponse,
    VehicleResponse,
    VehicleUpdateRequest,
)
from backend.services.logistics_service import LogisticsService

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def _to_vehicle_response(veh) -> VehicleResponse:
    return VehicleResponse(
        id=veh.id,
        registration_number=veh.registration_number,
        vehicle_code=veh.vehicle_code,
        vehicle_type=veh.vehicle_type,
        capacity_kg=veh.capacity_kg,
        status=veh.status,
        is_active=veh.is_active,
        assigned_driver_id=veh.assigned_driver_id,
        created_at=veh.created_at,
        updated_at=veh.updated_at,
    )


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    payload: VehicleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> VehicleResponse:
    """Registers a new vehicle in the logistics fleet. Requires dispatcher or admin role."""
    service = LogisticsService(session)
    veh = await service.register_vehicle(payload, actor_id=current_user.id)
    return _to_vehicle_response(veh)


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[str | None, Query(description="Filter by vehicle status")] = None,
    vehicle_type: Annotated[str | None, Query(description="Filter by vehicle type")] = None,
    is_active: Annotated[bool | None, Query(description="Filter active/inactive")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VehicleListResponse:
    """Lists vehicles in the logistics fleet with filtering."""
    service = LogisticsService(session)
    total, items = await service.list_vehicles(
        status_filter=status,
        vehicle_type=vehicle_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return VehicleListResponse(
        total=total,
        items=[_to_vehicle_response(v) for v in items],
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VehicleResponse:
    """Retrieves vehicle details by ID."""
    service = LogisticsService(session)
    veh = await service.get_vehicle(vehicle_id)
    return _to_vehicle_response(veh)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    payload: VehicleUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> VehicleResponse:
    """Updates vehicle operational status and attributes. Requires dispatcher or admin role."""
    service = LogisticsService(session)
    veh = await service.update_vehicle(vehicle_id, payload, actor_id=current_user.id)
    return _to_vehicle_response(veh)


@router.post("/{vehicle_id}/locations", response_model=VehicleLocationResponse, status_code=status.HTTP_201_CREATED)
@router.post("/{vehicle_id}/location", response_model=VehicleLocationResponse, status_code=status.HTTP_201_CREATED)
async def ingest_vehicle_location(
    vehicle_id: uuid.UUID,
    payload: VehicleLocationCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin"]))],
) -> VehicleLocationResponse:
    """
    Ingests a GPS tracking observation for a vehicle.
    Snaps to road segment, validates monotonicity, updates Redis cache, and persists in PostgreSQL.
    """
    service = LogisticsService(session)
    if current_user.role == "driver":
        vehicle = await service.get_vehicle(vehicle_id)
        if vehicle.assigned_driver_id is not None and vehicle.assigned_driver_id != current_user.id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Drivers may not report telemetry for another driver's assigned vehicle.",
            )
    loc = await service.record_vehicle_location(vehicle_id, payload, actor_id=current_user.id)
    return VehicleLocationResponse(
        id=loc.id,
        vehicle_id=loc.vehicle_id,
        trip_id=loc.trip_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_kmh=loc.speed_kmh,
        heading_deg=loc.heading_deg,
        matched_segment_id=loc.matched_segment_id,
        snapping_distance_m=loc.snapping_distance_m,
        source=loc.source,
        recorded_at=loc.recorded_at,
        created_at=loc.created_at,
    )


@router.post("/{vehicle_id}/locations/batch", response_model=VehicleLocationBatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_vehicle_locations_batch(
    vehicle_id: uuid.UUID,
    payload: VehicleLocationBatchCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["driver", "dispatcher", "admin", "service_worker"]))],
) -> VehicleLocationBatchResponse:
    """
    Batch ingests time-series GPS fixes for a vehicle reconnecting after an offline period.
    Sorts chronologically, deduplicates timestamps, snaps coordinates, and updates latest position in Redis.
    """
    service = LogisticsService(session)
    persisted = await service.record_vehicle_locations_batch(
        vehicle_id=vehicle_id,
        payload_locations=payload.locations,
        actor_id=current_user.id,
    )
    items = []
    for loc in persisted:
        lat = loc.latitude if hasattr(loc, "latitude") else 0.0
        lon = loc.longitude if hasattr(loc, "longitude") else 0.0
        # If coordinates on geometry
        if lat == 0.0 and loc.geom is not None:
            from backend.services.evidence_service import extract_evidence_coordinates
            lat, lon = extract_evidence_coordinates(loc.geom)
        items.append(
            VehicleLocationResponse(
                id=loc.id,
                vehicle_id=loc.vehicle_id,
                trip_id=loc.trip_id,
                latitude=float(lat or 0.0),
                longitude=float(lon or 0.0),
                speed_kmh=loc.speed_kmh,
                heading_deg=loc.heading_deg,
                matched_segment_id=loc.matched_segment_id,
                snapping_distance_m=loc.snapping_distance_m,
                source=loc.source,
                recorded_at=loc.recorded_at,
                created_at=loc.created_at,
            )
        )
    return VehicleLocationBatchResponse(
        ingested_count=len(persisted),
        rejected_count=len(payload.locations) - len(persisted),
        items=items,
    )


@router.post("/telemetry/batch", response_model=VehicleLocationBatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_multi_vehicle_telemetry(
    payload: MultiVehicleTelemetryBatchRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker", "driver"]))],
) -> VehicleLocationBatchResponse:
    """
    Batch ingests telemetry across multiple fleet vehicles in one payload.
    """
    service = LogisticsService(session)
    # Group by vehicle_id
    grouped: dict[uuid.UUID, list[VehicleLocationCreateRequest]] = {}
    for item in payload.observations:
        v_id = item.vehicle_id
        if v_id not in grouped:
            grouped[v_id] = []
        loc_req = VehicleLocationCreateRequest(
            latitude=item.latitude,
            longitude=item.longitude,
            recorded_at=item.recorded_at,
            speed_kmh=item.speed_kmh,
            heading_deg=item.heading_deg,
            source=item.source,
            trip_id=item.trip_id,
        )
        grouped[v_id].append(loc_req)

    total_persisted: list[VehicleLocation] = []
    for v_id, locs in grouped.items():
        res = await service.record_vehicle_locations_batch(
            vehicle_id=v_id,
            payload_locations=locs,
            actor_id=current_user.id,
        )
        total_persisted.extend(res)

    items = []
    for loc in total_persisted:
        lat = 0.0
        lon = 0.0
        if loc.geom is not None:
            from backend.services.evidence_service import extract_evidence_coordinates
            lat, lon = extract_evidence_coordinates(loc.geom)
        items.append(
            VehicleLocationResponse(
                id=loc.id,
                vehicle_id=loc.vehicle_id,
                trip_id=loc.trip_id,
                latitude=float(lat or 0.0),
                longitude=float(lon or 0.0),
                speed_kmh=loc.speed_kmh,
                heading_deg=loc.heading_deg,
                matched_segment_id=loc.matched_segment_id,
                snapping_distance_m=loc.snapping_distance_m,
                source=loc.source,
                recorded_at=loc.recorded_at,
                created_at=loc.created_at,
            )
        )

    return VehicleLocationBatchResponse(
        ingested_count=len(total_persisted),
        rejected_count=len(payload.observations) - len(total_persisted),
        items=items,
    )


@router.get("/{vehicle_id}/location", response_model=LatestVehicleLocationResponse)
async def get_latest_location(
    vehicle_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LatestVehicleLocationResponse:
    """Retrieves the latest reported location for a vehicle from Redis (fallback PostgreSQL)."""
    service = LogisticsService(session)
    if current_user.role == "driver":
        vehicle = await service.get_vehicle(vehicle_id)
        if vehicle.assigned_driver_id is not None and vehicle.assigned_driver_id != current_user.id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Drivers may not access telemetry for another driver's assigned vehicle.",
            )
    loc = await service.get_latest_vehicle_location(vehicle_id)
    if not loc:
        # Check vehicle exists
        await service.get_vehicle(vehicle_id)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No location telemetry recorded for vehicle '{vehicle_id}'.",
        )
    return loc


@router.get("/{vehicle_id}/locations", response_model=VehicleLocationListResponse)
async def get_vehicle_location_history(
    vehicle_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VehicleLocationListResponse:
    """Retrieves time-series GPS location history for a vehicle."""
    service = LogisticsService(session)
    vehicle = await service.get_vehicle(vehicle_id)
    if current_user.role == "driver" and vehicle.assigned_driver_id is not None and vehicle.assigned_driver_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Drivers may not access telemetry for another driver's assigned vehicle.",
        )

    count_res = await session.execute(
        select(func.count(VehicleLocation.id)).where(VehicleLocation.vehicle_id == vehicle_id)
    )
    total = count_res.scalar() or 0

    query = (
        select(
            VehicleLocation,
            func.ST_Y(VehicleLocation.geom).label("lat"),
            func.ST_X(VehicleLocation.geom).label("lon"),
        )
        .where(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(VehicleLocation.recorded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(query)

    items = []
    for loc, lat, lon in res.all():
        items.append(
            VehicleLocationResponse(
                id=loc.id,
                vehicle_id=loc.vehicle_id,
                trip_id=loc.trip_id,
                latitude=float(lat),
                longitude=float(lon),
                speed_kmh=loc.speed_kmh,
                heading_deg=loc.heading_deg,
                matched_segment_id=loc.matched_segment_id,
                snapping_distance_m=loc.snapping_distance_m,
                source=loc.source,
                recorded_at=loc.recorded_at,
                created_at=loc.created_at,
            )
        )

    return VehicleLocationListResponse(total=total, items=items)
