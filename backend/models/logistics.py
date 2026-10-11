"""Logistics models: vehicles, GPS locations, deliveries, and trips."""

import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Vehicle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Transport vehicle in the logistics fleet."""
    __tablename__ = "vehicles"

    registration_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="truck", nullable=False)
    capacity_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    locations: Mapped[list["VehicleLocation"]] = relationship(
        "VehicleLocation",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip",
        back_populates="vehicle",
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
    source: Mapped[str] = mapped_column(String(50), default="gps", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="locations",
    )


class Delivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Essential cargo delivery consignment."""
    __tablename__ = "deliveries"

    tracking_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    cargo_class: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20),
        default="standard",
        nullable=False,
        comment="standard, critical, emergency",
    )
    origin_address: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    destination_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True, nullable=False)

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
    status: Mapped[str] = mapped_column(
        String(30),
        default="scheduled",
        index=True,
        nullable=False,
        comment="scheduled, active, completed, cancelled",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="trips")
    delivery: Mapped["Delivery | None"] = relationship("Delivery", back_populates="trips")
