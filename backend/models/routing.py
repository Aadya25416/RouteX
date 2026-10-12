import enum
import uuid
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class RouteMode(str, enum.Enum):
    SHORTEST_DISTANCE = "SHORTEST_DISTANCE"
    FASTEST_SAFE = "FASTEST_SAFE"


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
        default=RouteMode.SHORTEST_DISTANCE.value,
        nullable=False,
        comment="SHORTEST_DISTANCE, FASTEST_SAFE",
    )
    ordered_segment_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    ordered_node_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    snapped_origin_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapped_destination_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapped_origin_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapped_destination_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    eta_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score_summary: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    meets_safety_policy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avoided_hazard_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

