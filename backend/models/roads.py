"""Road network graph models: nodes, segments, and operational state."""

import enum
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class RoadStatus(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    OPEN = "OPEN"
    AT_RISK = "AT_RISK"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"


class RoadNode(Base, TimestampMixin):
    """Canonical intersection or endpoint node in the directed road graph."""
    __tablename__ = "road_nodes"

    # Canonical internal node ID, e.g. "node_osm_123456"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    osm_node_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    outgoing_segments: Mapped[list["RoadSegment"]] = relationship(
        "RoadSegment",
        foreign_keys="RoadSegment.u_node_id",
        back_populates="u_node",
        cascade="all, delete-orphan",
    )
    incoming_segments: Mapped[list["RoadSegment"]] = relationship(
        "RoadSegment",
        foreign_keys="RoadSegment.v_node_id",
        back_populates="v_node",
        cascade="all, delete-orphan",
    )


class RoadSegment(Base, TimestampMixin):
    """Traversable directed edge between two road nodes."""
    __tablename__ = "road_segments"

    # Canonical internal stable segment ID, e.g. "edge_u_v_k"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    osm_way_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)

    u_node_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_nodes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    v_node_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_nodes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    key: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    base_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    base_travel_time_s: Mapped[float] = mapped_column(Float, nullable=False)

    road_class: Mapped[str] = mapped_column(String(50), default="unclassified", index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oneway: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bridge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tunnel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    corridor_name: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)

    # Node relationships
    u_node: Mapped["RoadNode"] = relationship(
        "RoadNode",
        foreign_keys=[u_node_id],
        back_populates="outgoing_segments",
    )
    v_node: Mapped["RoadNode"] = relationship(
        "RoadNode",
        foreign_keys=[v_node_id],
        back_populates="incoming_segments",
    )

    # Operational state relationship
    state: Mapped["RoadSegmentState | None"] = relationship(
        "RoadSegmentState",
        back_populates="segment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class RoadSegmentState(Base, UUIDPrimaryKeyMixin):
    """Dynamic operational accessibility, safety scoring, and disruption state."""
    __tablename__ = "road_segment_state"

    road_segment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Operational status: default UNKNOWN per PRD requirements
    status: Mapped[str] = mapped_column(
        String(30),
        default=RoadStatus.UNKNOWN.value,
        nullable=False,
        index=True,
    )

    # Safety score convention: 0-100 where 100 means safer
    safety_score: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
    )

    # Disruption probability: 0.0 - 1.0
    disruption_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Model confidence: 0.0 - 1.0
    score_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    score_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status_reason_codes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("safety_score >= 0.0 AND safety_score <= 100.0", name="chk_safety_score_range"),
        CheckConstraint(
            "disruption_probability IS NULL OR (disruption_probability >= 0.0 AND disruption_probability <= 1.0)",
            name="chk_disruption_prob_range",
        ),
        CheckConstraint(
            "score_confidence IS NULL OR (score_confidence >= 0.0 AND score_confidence <= 1.0)",
            name="chk_score_confidence_range",
        ),
    )

    segment: Mapped["RoadSegment"] = relationship(
        "RoadSegment",
        back_populates="state",
    )
