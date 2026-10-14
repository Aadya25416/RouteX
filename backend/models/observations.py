from datetime import datetime
import uuid
from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class WeatherObservation(Base, UUIDPrimaryKeyMixin):
    """Normalized weather observation or forecast reading."""
    __tablename__ = "weather_observations"

    provider: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    data_type: Mapped[str] = mapped_column(
        String(20),
        default="CURRENT",
        nullable=False,
        index=True,
        comment="CURRENT, OBSERVATION, FORECAST, DAILY_SUMMARY",
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    # Core measurements & forecasts
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)  # Legacy / liquid rain mm
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)  # Total interval precipitation mm
    rain_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    showers_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    snowfall_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_probability_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dew_point_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_msl_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    surface_pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_gusts_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    visibility_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    et0_evapotranspiration_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_moisture_m3m3: Mapped[float | None] = mapped_column(Float, nullable=True)

    road_segment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    forecast_valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    issue_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


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


class TrafficObservation(Base, UUIDPrimaryKeyMixin):
    """Segment-level traffic conditions derived from vehicle GPS tracks."""
    __tablename__ = "traffic_observations"

    road_segment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    congestion_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(30),
        default="INSUFFICIENT_DATA",
        nullable=False,
        comment="HIGH, MEDIUM, LOW, INSUFFICIENT_DATA",
    )
    data_freshness_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    road_segment: Mapped["RoadSegment | None"] = relationship(  # noqa: F821
        "RoadSegment",
    )


class SatelliteIngestionLog(Base, UUIDPrimaryKeyMixin):
    """Audit record for ingested satellite scenes preventing duplicate processing."""
    __tablename__ = "satellite_ingestion_logs"

    scene_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cloud_cover_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    footprint_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incident_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
