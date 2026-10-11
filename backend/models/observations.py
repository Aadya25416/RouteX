"""Environmental observation models: weather stations/forecasts and remote sensing/satellite candidates."""

from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Float,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class WeatherObservation(Base, UUIDPrimaryKeyMixin):
    """Normalized weather observation or forecast reading."""
    __tablename__ = "weather_observations"

    provider: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    location_geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    visibility_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SatelliteEvent(Base, UUIDPrimaryKeyMixin):
    """Remote sensing or satellite candidate detection."""
    __tablename__ = "satellite_events"

    scene_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    candidate_geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True),
        nullable=False,
    )
    event_class: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="possible_flood, landslide_scar, surface_obstruction",
    )
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="candidate",
        index=True,
        nullable=False,
        comment="candidate, confirmed, discarded",
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
