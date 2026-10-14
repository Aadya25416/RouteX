"""Logistics service managing vehicles, deliveries, trips, GPS tracking, and route disruption validation."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_Distance, ST_MakePoint, ST_SetSRID
import redis.asyncio as aioredis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.logistics import (
    CargoType,
    Delivery,
    DeliveryPriority,
    DeliveryStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
)
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.models.routing import RouteMode, RouteRecommendation
from backend.models.users import User
from backend.schemas.logistics import (
    DeliveryCreateRequest,
    DeliveryResponse,
    DeliveryUpdateRequest,
    LatestVehicleLocationResponse,
    VehicleCreateRequest,
    VehicleLocationCreateRequest,
    VehicleLocationResponse,
    VehicleResponse,
    VehicleUpdateRequest,
)
from backend.schemas.routing import RerouteResponse
from backend.services.events import EventPublisher, record_audit_log
from backend.services.routing_engine import RoutingEngine

logger = logging.getLogger(__name__)
settings = get_settings()


class LogisticsService:
    """Core domain service for vehicles, deliveries, trips, GPS tracking, and disruption rerouting."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()
        self.routing_engine = RoutingEngine(session)

    # ==========================================
    # VEHICLE MANAGEMENT
    # ==========================================

    async def register_vehicle(
        self,
        payload: VehicleCreateRequest,
        actor_id: uuid.UUID | None = None,
    ) -> Vehicle:
        """Registers a new fleet vehicle with uniqueness validation."""
        # Check uniqueness of registration_number
        existing_reg = await self.session.execute(
            select(Vehicle).where(Vehicle.registration_number == payload.registration_number.strip().upper())
        )
        if existing_reg.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle with registration '{payload.registration_number}' already exists.",
            )

        # Check uniqueness of vehicle_code
        if payload.vehicle_code:
            existing_code = await self.session.execute(
                select(Vehicle).where(Vehicle.vehicle_code == payload.vehicle_code.strip().upper())
            )
            if existing_code.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle with code '{payload.vehicle_code}' already exists.",
                )

        # Check driver exists if assigned
        if payload.assigned_driver_id:
            driver = await self.session.get(User, payload.assigned_driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assigned driver user '{payload.assigned_driver_id}' not found.",
                )

        vehicle = Vehicle(
            registration_number=payload.registration_number.strip().upper(),
            vehicle_code=payload.vehicle_code.strip().upper() if payload.vehicle_code else None,
            vehicle_type=payload.vehicle_type,
            capacity_kg=payload.capacity_kg,
            status=payload.status.value,
            assigned_driver_id=payload.assigned_driver_id,
            is_active=True,
        )
        self.session.add(vehicle)
        await self.session.flush()

        record_audit_log(
            session=self.session,
            action="vehicle_registered",
            entity_type="vehicle",
            entity_id=str(vehicle.id),
            actor_id=actor_id,
            details={
                "registration_number": vehicle.registration_number,
                "vehicle_code": vehicle.vehicle_code,
                "status": vehicle.status,
            },
        )
        await self.session.commit()
        await self.session.refresh(vehicle)
        return vehicle

    async def get_vehicle(self, vehicle_id: uuid.UUID) -> Vehicle:
        vehicle = await self.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle '{vehicle_id}' not found.",
            )
        return vehicle

    async def list_vehicles(
        self,
        status_filter: str | None = None,
        vehicle_type: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[Vehicle]]:
        query = select(Vehicle)
        count_query = select(func.count(Vehicle.id))

        if status_filter:
            query = query.where(Vehicle.status == status_filter.upper())
            count_query = count_query.where(Vehicle.status == status_filter.upper())
        if vehicle_type:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
            count_query = count_query.where(Vehicle.vehicle_type == vehicle_type)
        if is_active is not None:
            query = query.where(Vehicle.is_active == is_active)
            count_query = count_query.where(Vehicle.is_active == is_active)

        total = (await self.session.execute(count_query)).scalar() or 0
        res = await self.session.execute(query.order_by(Vehicle.created_at.desc()).limit(limit).offset(offset))
        return total, list(res.scalars().all())

    async def update_vehicle(
        self,
        vehicle_id: uuid.UUID,
        payload: VehicleUpdateRequest,
        actor_id: uuid.UUID | None = None,
    ) -> Vehicle:
        vehicle = await self.get_vehicle(vehicle_id)

        if payload.assigned_driver_id is not None:
            driver = await self.session.get(User, payload.assigned_driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assigned driver user '{payload.assigned_driver_id}' not found.",
                )
            vehicle.assigned_driver_id = payload.assigned_driver_id

        if payload.vehicle_type is not None:
            vehicle.vehicle_type = payload.vehicle_type
        if payload.capacity_kg is not None:
            vehicle.capacity_kg = payload.capacity_kg
        if payload.status is not None:
            vehicle.status = payload.status.value
        if payload.is_active is not None:
            vehicle.is_active = payload.is_active

        record_audit_log(
            session=self.session,
            action="vehicle_updated",
            entity_type="vehicle",
            entity_id=str(vehicle.id),
            actor_id=actor_id,
            details=payload.model_dump(exclude_unset=True),
        )
        await self.session.commit()
        await self.session.refresh(vehicle)
        return vehicle

    # ==========================================
    # DELIVERY MANAGEMENT
    # ==========================================

    async def create_delivery(
        self,
        payload: DeliveryCreateRequest,
        actor_id: uuid.UUID | None = None,
    ) -> Delivery:
        """Creates a new essential supply delivery consignment."""
        # Validate tracking code uniqueness
        existing_code = await self.session.execute(
            select(Delivery).where(Delivery.tracking_code == payload.tracking_code.strip().upper())
        )
        if existing_code.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Delivery with tracking code '{payload.tracking_code}' already exists.",
            )

        # Build point geometries
        origin_geom = ST_SetSRID(ST_MakePoint(payload.origin_lon, payload.origin_lat), 4326)
        dest_geom = ST_SetSRID(ST_MakePoint(payload.destination_lon, payload.destination_lat), 4326)

        delivery = Delivery(
            tracking_code=payload.tracking_code.strip().upper(),
            cargo_type=payload.cargo_type.value,
            cargo_class=payload.cargo_class,
            description=payload.description,
            priority=payload.priority.value,
            origin_address=payload.origin_address,
            origin_name=payload.origin_name,
            origin_geom=origin_geom,
            destination_address=payload.destination_address,
            destination_name=payload.destination_name,
            destination_geom=dest_geom,
            deadline=payload.deadline,
            status=DeliveryStatus.PENDING.value,
        )
        self.session.add(delivery)
        await self.session.flush()

        record_audit_log(
            session=self.session,
            action="delivery_created",
            entity_type="delivery",
            entity_id=str(delivery.id),
            actor_id=actor_id,
            details={
                "tracking_code": delivery.tracking_code,
                "cargo_type": delivery.cargo_type,
                "priority": delivery.priority,
            },
        )
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery

    async def get_delivery(self, delivery_id: uuid.UUID) -> Delivery:
        delivery = await self.session.get(Delivery, delivery_id)
        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery '{delivery_id}' not found.",
            )
        return delivery

    async def list_deliveries(
        self,
        status_filter: str | None = None,
        cargo_type: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[Delivery]]:
        query = select(Delivery)
        count_query = select(func.count(Delivery.id))

        if status_filter:
            query = query.where(Delivery.status == status_filter.upper())
            count_query = count_query.where(Delivery.status == status_filter.upper())
        if cargo_type:
            query = query.where(Delivery.cargo_type == cargo_type.upper())
            count_query = count_query.where(Delivery.cargo_type == cargo_type.upper())
        if priority:
            query = query.where(Delivery.priority == priority.upper())
            count_query = count_query.where(Delivery.priority == priority.upper())

        total = (await self.session.execute(count_query)).scalar() or 0
        res = await self.session.execute(query.order_by(Delivery.created_at.desc()).limit(limit).offset(offset))
        return total, list(res.scalars().all())

    async def update_delivery(
        self,
        delivery_id: uuid.UUID,
        payload: DeliveryUpdateRequest,
        actor_id: uuid.UUID | None = None,
    ) -> Delivery:
        delivery = await self.get_delivery(delivery_id)

        if payload.description is not None:
            delivery.description = payload.description
        if payload.priority is not None:
            delivery.priority = payload.priority.value
        if payload.status is not None:
            delivery.status = payload.status.value
        if payload.deadline is not None:
            delivery.deadline = payload.deadline

        record_audit_log(
            session=self.session,
            action="delivery_updated",
            entity_type="delivery",
            entity_id=str(delivery.id),
            actor_id=actor_id,
            details=payload.model_dump(exclude_unset=True),
        )
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery

    # ==========================================
    # TRIP MANAGEMENT & VEHICLE ASSIGNMENT
    # ==========================================

    async def create_and_assign_trip(
        self,
        vehicle_id: uuid.UUID,
        delivery_id: uuid.UUID,
        driver_id: uuid.UUID | None = None,
        routing_mode: RouteMode = RouteMode.SHORTEST_DISTANCE,
        require_verified_safe: bool = False,
        actor_id: uuid.UUID | None = None,
    ) -> Trip:
        """
        Creates a trip, validates vehicle and delivery availability,
        plans initial route recommendation, and locks state atomically.
        """
        vehicle = await self.get_vehicle(vehicle_id)
        if not vehicle.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{vehicle_id}' is deactivated.",
            )
        if vehicle.status in [VehicleStatus.IN_TRANSIT.value, VehicleStatus.MAINTENANCE.value, VehicleStatus.DECOMMISSIONED.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle '{vehicle_id}' cannot be assigned; current status is '{vehicle.status}'.",
            )

        # Check existing active trips for vehicle
        active_veh_trip = await self.session.execute(
            select(Trip).where(
                Trip.vehicle_id == vehicle_id,
                Trip.status.in_([TripStatus.PLANNED.value, TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]),
            )
        )
        if active_veh_trip.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Vehicle '{vehicle_id}' already has an active or planned trip assignment.",
            )

        delivery = await self.get_delivery(delivery_id)
        if delivery.status not in [DeliveryStatus.PENDING.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Delivery '{delivery_id}' cannot be assigned; current status is '{delivery.status}'.",
            )

        # Check driver if specified
        assigned_driver_id = driver_id or vehicle.assigned_driver_id
        if assigned_driver_id:
            driver = await self.session.get(User, assigned_driver_id)
            if not driver:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Driver user '{assigned_driver_id}' not found.",
                )

        # Extract delivery origin/dest coordinates
        coords_res = await self.session.execute(
            select(
                func.ST_Y(delivery.origin_geom).label("orig_lat"),
                func.ST_X(delivery.origin_geom).label("orig_lon"),
                func.ST_Y(delivery.destination_geom).label("dest_lat"),
                func.ST_X(delivery.destination_geom).label("dest_lon"),
            ).where(Delivery.id == delivery_id)
        )
        coords = coords_res.first()
        if not coords or coords.orig_lat is None or coords.dest_lat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery coordinates are invalid or missing.",
            )

        # Calculate initial route
        route_rec = await self.routing_engine.calculate_route(
            origin_lat=coords.orig_lat,
            origin_lon=coords.orig_lon,
            destination_lat=coords.dest_lat,
            destination_lon=coords.dest_lon,
            mode=routing_mode,
            require_verified_safe=require_verified_safe,
            persist=True,
            reason=f"Initial planned route for delivery {delivery.tracking_code}",
        )

        trip = Trip(
            vehicle_id=vehicle_id,
            delivery_id=delivery_id,
            driver_id=assigned_driver_id,
            current_route_id=route_rec.id,
            status=TripStatus.PLANNED.value,
            estimated_duration_s=route_rec.eta_seconds,
            estimated_distance_m=route_rec.distance_m,
        )
        self.session.add(trip)

        # Update vehicle & delivery states
        vehicle.status = VehicleStatus.ASSIGNED.value
        delivery.status = DeliveryStatus.ASSIGNED.value

        await self.session.flush()

        # Link route recommendation to trip
        if route_rec.id:
            db_route = await self.session.get(RouteRecommendation, route_rec.id)
            if db_route:
                db_route.trip_id = trip.id

        record_audit_log(
            session=self.session,
            action="trip_assigned",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={
                "vehicle_id": str(vehicle_id),
                "delivery_id": str(delivery_id),
                "route_id": str(route_rec.id),
                "distance_m": route_rec.distance_m,
                "eta_s": route_rec.eta_seconds,
            },
        )
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def get_trip(self, trip_id: uuid.UUID) -> Trip:
        trip = await self.session.execute(
            select(Trip)
            .options(
                selectinload(Trip.vehicle),
                selectinload(Trip.delivery),
                selectinload(Trip.current_route),
            )
            .where(Trip.id == trip_id)
        )
        res = trip.scalar_one_or_none()
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trip '{trip_id}' not found.",
            )
        return res

    async def list_trips(
        self,
        status_filter: str | None = None,
        vehicle_id: uuid.UUID | None = None,
        delivery_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[Trip]]:
        query = select(Trip).options(
            selectinload(Trip.vehicle),
            selectinload(Trip.delivery),
        )
        count_query = select(func.count(Trip.id))

        if status_filter:
            query = query.where(Trip.status == status_filter.upper())
            count_query = count_query.where(Trip.status == status_filter.upper())
        if vehicle_id:
            query = query.where(Trip.vehicle_id == vehicle_id)
            count_query = count_query.where(Trip.vehicle_id == vehicle_id)
        if delivery_id:
            query = query.where(Trip.delivery_id == delivery_id)
            count_query = count_query.where(Trip.delivery_id == delivery_id)
        if driver_id:
            query = query.where(Trip.driver_id == driver_id)
            count_query = count_query.where(Trip.driver_id == driver_id)

        total = (await self.session.execute(count_query)).scalar() or 0
        res = await self.session.execute(query.order_by(Trip.created_at.desc()).limit(limit).offset(offset))
        return total, list(res.scalars().all())

    async def start_trip(self, trip_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> Trip:
        """Transitions trip from PLANNED to IN_TRANSIT and updates vehicle and delivery."""
        trip = await self.get_trip(trip_id)
        if trip.status != TripStatus.PLANNED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start trip in state '{trip.status}'. Must be {TripStatus.PLANNED.value}.",
            )

        now = datetime.now(timezone.utc)
        trip.status = TripStatus.IN_TRANSIT.value
        trip.started_at = now

        if trip.vehicle:
            trip.vehicle.status = VehicleStatus.IN_TRANSIT.value
        if trip.delivery:
            trip.delivery.status = DeliveryStatus.IN_TRANSIT.value

        record_audit_log(
            session=self.session,
            action="trip_started",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={"started_at": now.isoformat()},
        )
        await self.session.commit()
        await self.publisher.publish_event(
            event_type="trip.started",
            entity_id=str(trip.id),
            payload={"trip_id": str(trip.id), "vehicle_id": str(trip.vehicle_id)},
        )
        return trip

    async def pause_trip(self, trip_id: uuid.UUID, reason: str | None = None, actor_id: uuid.UUID | None = None) -> Trip:
        trip = await self.get_trip(trip_id)
        if trip.status != TripStatus.IN_TRANSIT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pause trip in state '{trip.status}'. Must be {TripStatus.IN_TRANSIT.value}.",
            )

        now = datetime.now(timezone.utc)
        trip.status = TripStatus.PAUSED.value
        trip.paused_at = now

        record_audit_log(
            session=self.session,
            action="trip_paused",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={"paused_at": now.isoformat(), "reason": reason},
        )
        await self.session.commit()
        return trip

    async def resume_trip(self, trip_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> Trip:
        trip = await self.get_trip(trip_id)
        if trip.status != TripStatus.PAUSED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume trip in state '{trip.status}'. Must be {TripStatus.PAUSED.value}.",
            )

        trip.status = TripStatus.IN_TRANSIT.value

        record_audit_log(
            session=self.session,
            action="trip_resumed",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={},
        )
        await self.session.commit()
        return trip

    async def complete_trip(self, trip_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> Trip:
        """Transitions trip to COMPLETED, marks delivery DELIVERED, and releases vehicle to AVAILABLE."""
        trip = await self.get_trip(trip_id)
        if trip.status not in [TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete trip in state '{trip.status}'. Must be IN_TRANSIT or PAUSED.",
            )

        now = datetime.now(timezone.utc)
        trip.status = TripStatus.COMPLETED.value
        trip.completed_at = now

        if trip.vehicle:
            trip.vehicle.status = VehicleStatus.AVAILABLE.value
        if trip.delivery:
            trip.delivery.status = DeliveryStatus.DELIVERED.value

        record_audit_log(
            session=self.session,
            action="trip_completed",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={"completed_at": now.isoformat()},
        )
        await self.session.commit()
        await self.publisher.publish_event(
            event_type="trip.completed",
            entity_id=str(trip.id),
            payload={"trip_id": str(trip.id), "vehicle_id": str(trip.vehicle_id)},
        )
        return trip

    async def cancel_trip(
        self,
        trip_id: uuid.UUID,
        cancellation_reason: str,
        actor_id: uuid.UUID | None = None,
    ) -> Trip:
        """Cancels a trip, releases vehicle to AVAILABLE, and returns delivery to PENDING."""
        trip = await self.get_trip(trip_id)
        if trip.status == TripStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel an already COMPLETED trip.",
            )

        trip.status = TripStatus.CANCELLED.value
        trip.cancellation_reason = cancellation_reason

        if trip.vehicle:
            trip.vehicle.status = VehicleStatus.AVAILABLE.value
        if trip.delivery:
            trip.delivery.status = DeliveryStatus.PENDING.value

        record_audit_log(
            session=self.session,
            action="trip_cancelled",
            entity_type="trip",
            entity_id=str(trip.id),
            actor_id=actor_id,
            details={"reason": cancellation_reason},
        )
        await self.session.commit()
        return trip

    # ==========================================
    # GPS LOCATION INGESTION
    # ==========================================

    async def record_vehicle_location(
        self,
        vehicle_id: uuid.UUID,
        payload: VehicleLocationCreateRequest,
        actor_id: uuid.UUID | None = None,
    ) -> VehicleLocation:
        """
        Ingests a GPS report, validates timestamp monotonicity, snaps to road segment,
        stores latest in Redis, and records history in PostgreSQL.
        """
        vehicle = await self.get_vehicle(vehicle_id)

        # Timezone validation
        if payload.recorded_at.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GPS recorded_at timestamp must be timezone-aware.",
            )

        # Monotonicity check against latest location
        latest_loc = await self.get_latest_vehicle_location(vehicle_id)
        if latest_loc and payload.recorded_at <= latest_loc.recorded_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Out-of-order GPS update rejected. Reported timestamp ({payload.recorded_at}) "
                    f"is not strictly newer than current latest position ({latest_loc.recorded_at})."
                ),
            )

        # Resolve trip_id
        active_trip_id = payload.trip_id
        if not active_trip_id:
            active_trip_query = await self.session.execute(
                select(Trip.id).where(
                    Trip.vehicle_id == vehicle_id,
                    Trip.status.in_([TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]),
                ).order_by(Trip.started_at.desc()).limit(1)
            )
            active_trip_id = active_trip_query.scalar_one_or_none()

        # Snap to nearest road segment using configured threshold
        matched_seg_id, snapping_dist = await self.routing_engine.snap_coordinate_to_segment(
            lat=payload.latitude, lon=payload.longitude, max_distance_m=settings.GPS_SNAP_THRESHOLD_M
        )

        # 1. Update Redis cache with latest location
        await self._cache_latest_location_redis(
            vehicle_id=vehicle_id,
            lat=payload.latitude,
            lon=payload.longitude,
            speed_kmh=payload.speed_kmh,
            heading_deg=payload.heading_deg,
            matched_segment_id=matched_seg_id,
            snapping_distance_m=snapping_dist,
            recorded_at=payload.recorded_at,
            trip_id=active_trip_id,
        )

        # 2. Persist in PostgreSQL
        pt_geom = ST_SetSRID(ST_MakePoint(payload.longitude, payload.latitude), 4326)
        loc = VehicleLocation(
            vehicle_id=vehicle_id,
            trip_id=active_trip_id,
            geom=pt_geom,
            speed_kmh=payload.speed_kmh,
            heading_deg=payload.heading_deg,
            matched_segment_id=matched_seg_id,
            snapping_distance_m=snapping_dist,
            source=payload.source,
            recorded_at=payload.recorded_at,
        )
        self.session.add(loc)
        await self.session.commit()
        await self.session.refresh(loc)
        return loc

    async def record_vehicle_locations_batch(
        self,
        vehicle_id: uuid.UUID,
        payload_locations: list[VehicleLocationCreateRequest],
        actor_id: uuid.UUID | None = None,
    ) -> list[VehicleLocation]:
        """
        Batch ingests time-series GPS fixes for a vehicle.
        Validates timestamps, deduplicates against existing records, snaps each point to nearby road,
        and records all valid points in PostgreSQL. Updates Redis with the latest chronologically.
        """
        vehicle = await self.get_vehicle(vehicle_id)
        if not payload_locations:
            return []

        # Sort chronologically by recorded_at
        sorted_locations = sorted(payload_locations, key=lambda x: x.recorded_at)

        # Resolve active trip if any
        active_trip_query = await self.session.execute(
            select(Trip.id).where(
                Trip.vehicle_id == vehicle_id,
                Trip.status.in_([TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]),
            ).order_by(Trip.started_at.desc()).limit(1)
        )
        active_trip_id = active_trip_query.scalar_one_or_none()

        persisted_locs: list[VehicleLocation] = []
        newest_point: tuple[VehicleLocationCreateRequest, str | None, float | None] | None = None

        for item in sorted_locations:
            if item.recorded_at.tzinfo is None:
                continue

            # Check if an identical timestamp observation already exists for this vehicle
            existing = await self.session.execute(
                select(VehicleLocation.id).where(
                    VehicleLocation.vehicle_id == vehicle_id,
                    VehicleLocation.recorded_at == item.recorded_at,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Snap coordinate using configured threshold
            matched_seg_id, snapping_dist = await self.routing_engine.snap_coordinate_to_segment(
                lat=item.latitude,
                lon=item.longitude,
                max_distance_m=settings.GPS_SNAP_THRESHOLD_M,
            )

            trip_id = item.trip_id or active_trip_id
            pt_geom = ST_SetSRID(ST_MakePoint(item.longitude, item.latitude), 4326)
            loc = VehicleLocation(
                vehicle_id=vehicle_id,
                trip_id=trip_id,
                geom=pt_geom,
                speed_kmh=item.speed_kmh,
                heading_deg=item.heading_deg,
                matched_segment_id=matched_seg_id,
                snapping_distance_m=snapping_dist,
                source=item.source,
                recorded_at=item.recorded_at,
            )
            self.session.add(loc)
            persisted_locs.append(loc)

            if newest_point is None or item.recorded_at > newest_point[0].recorded_at:
                newest_point = (item, matched_seg_id, snapping_dist)

        if persisted_locs:
            await self.session.commit()
            for loc in persisted_locs:
                await self.session.refresh(loc)

            # Update Redis with newest location if newer than current Redis cache
            if newest_point:
                item, seg_id, dist_m = newest_point
                latest_in_cache = await self.get_latest_vehicle_location(vehicle_id)
                if not latest_in_cache or item.recorded_at >= latest_in_cache.recorded_at:
                    await self._cache_latest_location_redis(
                        vehicle_id=vehicle_id,
                        lat=item.latitude,
                        lon=item.longitude,
                        speed_kmh=item.speed_kmh,
                        heading_deg=item.heading_deg,
                        matched_segment_id=seg_id,
                        snapping_distance_m=dist_m,
                        recorded_at=item.recorded_at,
                        trip_id=item.trip_id or active_trip_id,
                    )

        return persisted_locs

    async def _cache_latest_location_redis(
        self,
        vehicle_id: uuid.UUID,
        lat: float,
        lon: float,
        speed_kmh: float | None,
        heading_deg: float | None,
        matched_segment_id: str | None,
        snapping_distance_m: float | None,
        recorded_at: datetime,
        trip_id: uuid.UUID | None,
    ) -> None:
        """Stores the latest GPS fix in Redis."""
        try:
            client = aioredis.from_url(
                settings.redis_url,
                socket_connect_timeout=2.0,
                decode_responses=True,
            )
            key = f"vehicle:{vehicle_id}:latest_location"
            data = {
                "vehicle_id": str(vehicle_id),
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": speed_kmh,
                "heading_deg": heading_deg,
                "matched_segment_id": matched_segment_id,
                "snapping_distance_m": snapping_distance_m,
                "recorded_at": recorded_at.isoformat(),
                "trip_id": str(trip_id) if trip_id else None,
            }
            await client.set(key, json.dumps(data), ex=86400)
            await client.aclose()
        except Exception as exc:
            logger.warning(f"Could not cache vehicle location to Redis: {exc}")

    async def get_latest_vehicle_location(self, vehicle_id: uuid.UUID) -> LatestVehicleLocationResponse | None:
        """Retrieves latest vehicle location from Redis first, falling back to PostgreSQL."""
        # 1. Try Redis
        try:
            client = aioredis.from_url(
                settings.redis_url,
                socket_connect_timeout=2.0,
                decode_responses=True,
            )
            raw = await client.get(f"vehicle:{vehicle_id}:latest_location")
            await client.aclose()
            if raw:
                d = json.loads(raw)
                return LatestVehicleLocationResponse(
                    vehicle_id=uuid.UUID(d["vehicle_id"]),
                    latitude=float(d["latitude"]),
                    longitude=float(d["longitude"]),
                    speed_kmh=d.get("speed_kmh"),
                    heading_deg=d.get("heading_deg"),
                    matched_segment_id=d.get("matched_segment_id"),
                    snapping_distance_m=d.get("snapping_distance_m"),
                    recorded_at=datetime.fromisoformat(d["recorded_at"]),
                    trip_id=uuid.UUID(d["trip_id"]) if d.get("trip_id") else None,
                    source_cache="redis",
                )
        except Exception as exc:
            logger.debug(f"Redis fetch failed for latest location: {exc}")

        # 2. Fallback to PostgreSQL
        query = (
            select(
                VehicleLocation,
                func.ST_Y(VehicleLocation.geom).label("lat"),
                func.ST_X(VehicleLocation.geom).label("lon"),
            )
            .where(VehicleLocation.vehicle_id == vehicle_id)
            .order_by(VehicleLocation.recorded_at.desc())
            .limit(1)
        )
        res = await self.session.execute(query)
        row = res.first()
        if not row:
            return None

        loc_obj, lat, lon = row
        return LatestVehicleLocationResponse(
            vehicle_id=loc_obj.vehicle_id,
            latitude=float(lat),
            longitude=float(lon),
            speed_kmh=loc_obj.speed_kmh,
            heading_deg=loc_obj.heading_deg,
            matched_segment_id=loc_obj.matched_segment_id,
            snapping_distance_m=loc_obj.snapping_distance_m,
            recorded_at=loc_obj.recorded_at,
            trip_id=loc_obj.trip_id,
            source_cache="postgresql",
        )

    # ==========================================
    # DISRUPTION-AWARE ROUTE VALIDATION
    # ==========================================

    async def reroute_trip(
        self,
        trip_id: uuid.UUID,
        reason: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> RerouteResponse:
        """
        Recalculates route for a trip against current road conditions.
        If current route is blocked, finds an alternative route.
        """
        trip = await self.get_trip(trip_id)
        if trip.status not in [TripStatus.PLANNED.value, TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reroute trip in inactive state '{trip.status}'.",
            )

        if not trip.delivery:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trip does not have an associated delivery.",
            )

        # Check current route segments for blockages
        current_route = trip.current_route
        current_mode = RouteMode(current_route.mode) if current_route and current_route.mode in RouteMode.__members__ else RouteMode.SHORTEST_DISTANCE
        blocked_segments_on_route: list[str] = []

        if current_route and current_route.ordered_segment_ids:
            # Check DB status of these segments
            st_query = select(RoadSegmentState.road_segment_id).where(
                RoadSegmentState.road_segment_id.in_(current_route.ordered_segment_ids),
                RoadSegmentState.status == RoadStatus.BLOCKED.value,
            )
            blocked_res = await self.session.execute(st_query)
            blocked_segments_on_route = [r[0] for r in blocked_res.all()]

        # Determine start coordinates (current vehicle GPS location if in transit, else delivery origin)
        start_lat = None
        start_lon = None
        if trip.status == TripStatus.IN_TRANSIT.value:
            latest_gps = await self.get_latest_vehicle_location(trip.vehicle_id)
            if latest_gps:
                start_lat = latest_gps.latitude
                start_lon = latest_gps.longitude

        if start_lat is None or start_lon is None:
            # Use delivery origin
            coords_res = await self.session.execute(
                select(
                    func.ST_Y(trip.delivery.origin_geom).label("orig_lat"),
                    func.ST_X(trip.delivery.origin_geom).label("orig_lon"),
                    func.ST_Y(trip.delivery.destination_geom).label("dest_lat"),
                    func.ST_X(trip.delivery.destination_geom).label("dest_lon"),
                ).where(Delivery.id == trip.delivery_id)
            )
            c = coords_res.first()
            start_lat = c.orig_lat
            start_lon = c.orig_lon
            dest_lat = c.dest_lat
            dest_lon = c.dest_lon
        else:
            dest_res = await self.session.execute(
                select(
                    func.ST_Y(trip.delivery.destination_geom).label("dest_lat"),
                    func.ST_X(trip.delivery.destination_geom).label("dest_lon"),
                ).where(Delivery.id == trip.delivery_id)
            )
            c = dest_res.first()
            dest_lat = c.dest_lat
            dest_lon = c.dest_lon

        reroute_reason = reason or (
            f"Recalculated due to blockage on segment(s): {', '.join(blocked_segments_on_route)}"
            if blocked_segments_on_route
            else "Manual reroute requested by dispatcher."
        )

        try:
            new_route = await self.routing_engine.calculate_route(
                origin_lat=start_lat,
                origin_lon=start_lon,
                destination_lat=dest_lat,
                destination_lon=dest_lon,
                mode=current_mode,
                trip_id=trip.id,
                persist=True,
                reason=reroute_reason,
            )

            # Update trip with new route
            prev_route_id = trip.current_route_id
            if current_route:
                current_route.is_active = False

            trip.current_route_id = new_route.id
            trip.estimated_distance_m = new_route.distance_m
            trip.estimated_duration_s = new_route.eta_seconds

            record_audit_log(
                session=self.session,
                action="trip_rerouted",
                entity_type="trip",
                entity_id=str(trip.id),
                actor_id=actor_id,
                details={
                    "previous_route_id": str(prev_route_id),
                    "new_route_id": str(new_route.id),
                    "blocked_segments": blocked_segments_on_route,
                },
            )
            await self.session.commit()

            await self.publisher.publish_event(
                event_type="trip.rerouted",
                entity_id=str(trip.id),
                payload={
                    "trip_id": str(trip.id),
                    "new_route_id": str(new_route.id),
                    "blocked_segments": blocked_segments_on_route,
                },
            )

            return RerouteResponse(
                trip_id=trip.id,
                status="REROUTED",
                disruption_segment_ids=blocked_segments_on_route,
                previous_route_id=prev_route_id,
                new_route=new_route,
                message=f"Trip successfully rerouted. Avoided {len(blocked_segments_on_route)} blocked segments.",
            )

        except HTTPException as exc:
            if "NO_SAFE_ROUTE" in str(exc.detail):
                # No admissible route
                trip.cancellation_reason = f"Route disrupted by blockage: {blocked_segments_on_route}. No alternative route exists."
                record_audit_log(
                    session=self.session,
                    action="trip_reroute_failed",
                    entity_type="trip",
                    entity_id=str(trip.id),
                    actor_id=actor_id,
                    details={"blocked_segments": blocked_segments_on_route, "error": str(exc.detail)},
                )
                await self.session.commit()

                await self.publisher.publish_event(
                    event_type="trip.route_blocked",
                    entity_id=str(trip.id),
                    payload={
                        "trip_id": str(trip.id),
                        "blocked_segments": blocked_segments_on_route,
                    },
                )

                return RerouteResponse(
                    trip_id=trip.id,
                    status="NO_SAFE_ROUTE",
                    disruption_segment_ids=blocked_segments_on_route,
                    previous_route_id=trip.current_route_id,
                    new_route=None,
                    message="NO_SAFE_ROUTE: All alternative paths are blocked or unavailable under current safety policy.",
                )
            raise

    async def check_and_reroute_disrupted_trips(
        self,
        newly_blocked_segment_ids: list[str],
        actor_id: uuid.UUID | None = None,
    ) -> list[RerouteResponse]:
        """
        Scans all active trips and evaluates whether their current route includes
        any newly blocked segments. Triggers rerouting automatically.
        """
        if not newly_blocked_segment_ids:
            return []

        # Find active trips
        active_trips_res = await self.session.execute(
            select(Trip)
            .options(selectinload(Trip.current_route))
            .where(Trip.status.in_([TripStatus.PLANNED.value, TripStatus.IN_TRANSIT.value, TripStatus.PAUSED.value]))
        )
        active_trips = active_trips_res.scalars().all()

        responses: list[RerouteResponse] = []
        for trip in active_trips:
            if not trip.current_route or not trip.current_route.ordered_segment_ids:
                continue

            # Check overlap
            overlap = set(trip.current_route.ordered_segment_ids).intersection(set(newly_blocked_segment_ids))
            if overlap:
                logger.info(f"Trip {trip.id} route disrupted by blocked segments {overlap}. Recalculating route...")
                resp = await self.reroute_trip(
                    trip_id=trip.id,
                    reason=f"Automated disruption reroute: segments {list(overlap)} confirmed BLOCKED.",
                    actor_id=actor_id,
                )
                responses.append(resp)

        return responses
