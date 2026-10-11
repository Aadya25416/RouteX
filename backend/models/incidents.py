"""Incident reporting and evidence models."""

import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Incident(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Field or sensor reported road disruption incident."""
    __tablename__ = "incidents"

    incident_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    road_segment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="reported",
        index=True,
        nullable=False,
        comment="reported, confirmed, rejected, resolved",
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
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    evidence_items: Mapped[list["IncidentEvidence"]] = relationship(
        "IncidentEvidence",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentEvidence(Base, UUIDPrimaryKeyMixin):
    """Supporting photographs and candidate detections for incidents."""
    __tablename__ = "incident_evidence"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50),
        default="field_photo",
        nullable=False,
        comment="field_photo, satellite_scene, public_feed",
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_detection_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="evidence_items",
    )
