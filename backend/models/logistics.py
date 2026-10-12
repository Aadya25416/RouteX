"""Logistics models: vehicles, GPS locations, deliveries, and trips."""

import enum
import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    MAINTENANCE = "MAINTENANCE"
    DECOMMISSIONED = "DECOMMISSIONED"


class CargoType(str, enum.Enum):
    MEDICINE = "MEDICINE"
    FOOD = "FOOD"
    AGRICULTURAL_PRODUCE = "AGRICULTURAL_PRODUCE"
    CONSTRUCTION_MATERIALS = "CONSTRUCTION_MATERIALS"
    GENERAL = "GENERAL"


class DeliveryPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class TripStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    IN_TRANSIT = "IN_TRANSIT"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Vehicle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Transport vehicle in the logistics fleet."""
    __tablename__ = "vehicles"

    registration_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    vehicle_code: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="truck", nullable=False)
    capacity_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=VehicleStatus.AVAILABLE.value,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    locations: Mapped[list["VehicleLocation"]] = relationship(
        "VehicleLocation",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip",
        back_populates="vehicle",
    )
    assigned_driver: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[assigned_driver_id],
    )


class VehicleLocation(Base, UUIDPrimaryKeyMixin):
    """Time-stamped GPS track location for fleet vehicles."""
    __tablename__ = "vehicle_locations"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_segment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    snapping_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="gps", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="locations",
    )
    trip: Mapped["Trip | None"] = relationship(
        "Trip",
        back_populates="locations",
    )


class Delivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Essential cargo delivery consignment."""
    __tablename__ = "deliveries"

    tracking_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    cargo_type: Mapped[str] = mapped_column(
        String(50),
        default=CargoType.GENERAL.value,
        index=True,
        nullable=False,
    )
    cargo_class: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20),
        default=DeliveryPriority.NORMAL.value,
        index=True,
        nullable=False,
        comment="LOW, NORMAL, HIGH, CRITICAL",
    )
    origin_address: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    destination_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=DeliveryStatus.PENDING.value,
        index=True,
        nullable=False,
    )

    trips: Mapped[list["Trip"]] = relationship(
        "Trip",
        back_populates="delivery",
    )


class Trip(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Active assignment linking a vehicle, driver, and delivery."""
    __tablename__ = "trips"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    current_route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_recommendations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=TripStatus.PLANNED.value,
        index=True,
        nullable=False,
        comment="PLANNED, IN_TRANSIT, PAUSED, COMPLETED, CANCELLED",
    )
    estimated_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="trips")
    delivery: Mapped["Delivery | None"] = relationship("Delivery", back_populates="trips")
    driver: Mapped["User | None"] = relationship("User", foreign_keys=[driver_id])  # noqa: F821
    current_route: Mapped["RouteRecommendation | None"] = relationship(  # noqa: F821
        "RouteRecommendation",
        foreign_keys=[current_route_id],
    )
    locations: Mapped[list["VehicleLocation"]] = relationship(
        "VehicleLocation",
        back_populates="trip",
    )
