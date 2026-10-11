"""Routing recommendation model."""

import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class RouteRecommendation(Base, UUIDPrimaryKeyMixin):
    """Calculated route recommendation for a trip or ad-hoc dispatch."""
    __tablename__ = "route_recommendations"

    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="economical (shortest distance proxy), fastest_safe (emergency)",
    )
    ordered_segment_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    route_geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    eta_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score_summary: Mapped[float | None] = mapped_column(Float, nullable=True)
    avoided_hazard_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
