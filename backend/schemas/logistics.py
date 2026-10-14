"""Pydantic schemas for Logistics Management (Vehicles, Deliveries, Trips, GPS)."""

import uuid
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

from backend.models.logistics import (
    CargoType,
    DeliveryPriority,
    DeliveryStatus,
    TripStatus,
    VehicleStatus,
)
from backend.models.routing import RouteMode


# ==========================================
# Vehicle Schemas
# ==========================================

class VehicleCreateRequest(BaseModel):
    registration_number: Annotated[str, Field(min_length=2, max_length=50, description="Unique registration/license plate")]
    vehicle_code: Annotated[str | None, Field(max_length=50, default=None, description="Human-readable fleet code (e.g. TRK-01)")]
    vehicle_type: Annotated[str, Field(default="truck", max_length=50)]
    capacity_kg: Annotated[float | None, Field(ge=0.0, default=None)]
    assigned_driver_id: uuid.UUID | None = None
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleUpdateRequest(BaseModel):
    vehicle_type: Annotated[str | None, Field(max_length=50, default=None)]
    capacity_kg: Annotated[float | None, Field(ge=0.0, default=None)]
    assigned_driver_id: uuid.UUID | None = None
    status: VehicleStatus | None = None
    is_active: bool | None = None


class VehicleResponse(BaseModel):
    id: uuid.UUID
    registration_number: str
    vehicle_code: str | None = None
    vehicle_type: str
    capacity_kg: float | None = None
    status: str
    is_active: bool
    assigned_driver_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    total: int
    items: list[VehicleResponse]


# ==========================================
# Vehicle Location (GPS) Schemas
# ==========================================

class VehicleLocationCreateRequest(BaseModel):
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="Latitude in WGS84")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="Longitude in WGS84")]
    recorded_at: datetime = Field(description="Timezone-aware timestamp of the GPS observation")
    speed_kmh: Annotated[float | None, Field(ge=0.0, le=250.0, default=None)] = None
    heading_deg: Annotated[float | None, Field(ge=0.0, le=360.0, default=None)] = None
    source: Annotated[str, Field(default="gps", max_length=50)] = "gps"
    trip_id: uuid.UUID | None = None


class VehicleLocationResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    trip_id: uuid.UUID | None = None
    latitude: float
    longitude: float
    speed_kmh: float | None = None
    heading_deg: float | None = None
    matched_segment_id: str | None = None
    snapping_distance_m: float | None = None
    source: str
    recorded_at: datetime
    created_at: datetime


class VehicleLocationBatchCreateRequest(BaseModel):
    """Batch GPS observations for a vehicle reconnecting after offline period."""
    locations: list[VehicleLocationCreateRequest] = Field(min_length=1, max_length=200)


class MultiVehicleLocationItem(VehicleLocationCreateRequest):
    vehicle_id: uuid.UUID


class MultiVehicleTelemetryBatchRequest(BaseModel):
    """Batch GPS observations across multiple vehicles."""
    observations: list[MultiVehicleLocationItem] = Field(min_length=1, max_length=500)


class VehicleLocationBatchResponse(BaseModel):
    ingested_count: int
    rejected_count: int = 0
    items: list[VehicleLocationResponse]


class VehicleLocationListResponse(BaseModel):
    total: int
    items: list[VehicleLocationResponse]


class LatestVehicleLocationResponse(BaseModel):
    vehicle_id: uuid.UUID
    latitude: float
    longitude: float
    speed_kmh: float | None = None
    heading_deg: float | None = None
    matched_segment_id: str | None = None
    snapping_distance_m: float | None = None
    recorded_at: datetime
    trip_id: uuid.UUID | None = None
    source_cache: str = "redis"


# ==========================================
# Delivery Schemas
# ==========================================

class DeliveryCreateRequest(BaseModel):
    tracking_code: Annotated[str, Field(min_length=2, max_length=50, description="Unique consignment tracking code")]
    cargo_type: CargoType = CargoType.GENERAL
    cargo_class: Annotated[str, Field(default="general", max_length=50)] = "general"
    description: Annotated[str | None, Field(max_length=2000, default=None)] = None
    priority: DeliveryPriority = DeliveryPriority.NORMAL
    origin_address: Annotated[str, Field(min_length=2, max_length=255)]
    origin_name: Annotated[str | None, Field(max_length=255, default=None)] = None
    origin_lat: Annotated[float, Field(ge=-90.0, le=90.0, description="Origin latitude")]
    origin_lon: Annotated[float, Field(ge=-180.0, le=180.0, description="Origin longitude")]
    destination_address: Annotated[str, Field(min_length=2, max_length=255)]
    destination_name: Annotated[str | None, Field(max_length=255, default=None)] = None
    destination_lat: Annotated[float, Field(ge=-90.0, le=90.0, description="Destination latitude")]
    destination_lon: Annotated[float, Field(ge=-180.0, le=180.0, description="Destination longitude")]
    deadline: datetime | None = None


class DeliveryUpdateRequest(BaseModel):
    description: Annotated[str | None, Field(max_length=2000, default=None)] = None
    priority: DeliveryPriority | None = None
    status: DeliveryStatus | None = None
    deadline: datetime | None = None


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    tracking_code: str
    cargo_type: str
    cargo_class: str
    description: str | None = None
    priority: str
    origin_address: str
    origin_name: str | None = None
    origin_lat: float | None = None
    origin_lon: float | None = None
    destination_address: str
    destination_name: str | None = None
    destination_lat: float | None = None
    destination_lon: float | None = None
    deadline: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class DeliveryListResponse(BaseModel):
    total: int
    items: list[DeliveryResponse]


# ==========================================
# Trip Schemas
# ==========================================

class TripCreateRequest(BaseModel):
    vehicle_id: uuid.UUID
    delivery_id: uuid.UUID
    driver_id: uuid.UUID | None = None
    routing_mode: RouteMode = RouteMode.SHORTEST_DISTANCE
    require_verified_safe: bool = False


class TripUpdateRequest(BaseModel):
    driver_id: uuid.UUID | None = None
    cancellation_reason: Annotated[str | None, Field(max_length=1000, default=None)] = None


class TripPauseRequest(BaseModel):
    reason: Annotated[str | None, Field(max_length=500, default=None)] = None


class TripCancelRequest(BaseModel):
    cancellation_reason: Annotated[str, Field(min_length=3, max_length=1000)]


class TripResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    delivery_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    current_route_id: uuid.UUID | None = None
    status: str
    estimated_duration_s: float | None = None
    estimated_distance_m: float | None = None
    started_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    vehicle: VehicleResponse | None = None
    delivery: DeliveryResponse | None = None


class TripListResponse(BaseModel):
    total: int
    items: list[TripResponse]
