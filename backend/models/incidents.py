"""Incident reporting, road associations, and evidence models."""

import enum
import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class IncidentType(str, enum.Enum):
    LANDSLIDE = "LANDSLIDE"
    FLOOD = "FLOOD"
    ROAD_DAMAGE = "ROAD_DAMAGE"
    BRIDGE_DAMAGE = "BRIDGE_DAMAGE"
    TRAFFIC = "TRAFFIC"
    OTHER = "OTHER"


class IncidentSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    RESOLVED = "RESOLVED"


class AssociationType(str, enum.Enum):
    SUGGESTED = "SUGGESTED"
    VERIFIED = "VERIFIED"


class AssessedImpact(str, enum.Enum):
    AT_RISK = "AT_RISK"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"


class IncidentSource(str, enum.Enum):
    FIELD_REPORT = "FIELD_REPORT"
    CITIZEN = "CITIZEN"
    SENSOR = "SENSOR"


class Incident(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Field or sensor reported road disruption incident."""
    __tablename__ = "incidents"

    incident_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default=IncidentSeverity.MEDIUM.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    # Primary or legacy single road segment association (optional, maintained alongside association table)
    road_segment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=IncidentStatus.SUBMITTED.value,
        index=True,
        nullable=False,
        comment="SUBMITTED, UNDER_REVIEW, CONFIRMED, REJECTED, DUPLICATE, RESOLVED",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default=IncidentSource.FIELD_REPORT.value,
        nullable=False,
    )

    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Unique client report ID for idempotent offline sync
    client_report_id: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Review metadata
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Backwards compatibility with initial schema
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution metadata
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    evidence_items: Mapped[list["IncidentEvidence"]] = relationship(
        "IncidentEvidence",
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    road_associations: Mapped[list["IncidentRoadAssociation"]] = relationship(
        "IncidentRoadAssociation",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentRoadAssociation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Association between an incident and candidate or verified affected road segments."""
    __tablename__ = "incident_road_associations"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    road_segment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Distinguish between automatically suggested nearby road vs verified by an official
    association_type: Mapped[str] = mapped_column(
        String(30),
        default=AssociationType.SUGGESTED.value,
        nullable=False,
        index=True,
    )
    # Assessed impact: AT_RISK, RESTRICTED, BLOCKED
    assessed_impact: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="road_associations",
    )
    road_segment: Mapped["RoadSegment"] = relationship(  # noqa: F821
        "RoadSegment",
    )

    __table_args__ = (
        UniqueConstraint("incident_id", "road_segment_id", name="uq_incident_road_segment"),
    )


class IncidentEvidence(Base, UUIDPrimaryKeyMixin):
    """Supporting photographs and candidate detections for incidents."""
    __tablename__ = "incident_evidence"

    # Optional incident_id allows standalone raw evidence / satellite scene ingestion
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256_checksum: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    source_type: Mapped[str] = mapped_column(
        String(50),
        default="FIELD_OFFICER",
        nullable=False,
        comment="FIELD_OFFICER, SATELLITE, field_photo, satellite_scene, public_feed",
    )
    source_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    road_segment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    location_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    footprint_geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True),
        nullable=True,
    )
    acquisition_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="VALIDATED",
        nullable=False,
        comment="VALIDATED, REJECTED, SUSPICIOUS, PENDING_VALIDATION",
    )

    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        comment="PENDING, IN_PROGRESS, COMPLETED, FAILED",
    )
    claimed_by: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_detection_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    incident: Mapped["Incident | None"] = relationship(
        "Incident",
        back_populates="evidence_items",
    )
    road_segment: Mapped["RoadSegment | None"] = relationship(  # noqa: F821
        "RoadSegment",
    )
    uploader: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[uploader_id],
    )
