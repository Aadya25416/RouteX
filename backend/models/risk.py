"""Risk prediction model for ML / heuristic safety outputs."""

from datetime import datetime
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class RiskPrediction(Base, UUIDPrimaryKeyMixin):
    """Segment-level disruption probability and safety score predictions."""
    __tablename__ = "risk_predictions"

    road_segment_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("road_segments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    disruption_probability: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), default="heuristic_baseline", nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("safety_score >= 0.0 AND safety_score <= 100.0", name="chk_risk_safety_score_range"),
        CheckConstraint(
            "disruption_probability >= 0.0 AND disruption_probability <= 1.0",
            name="chk_risk_disruption_prob_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="chk_risk_confidence_range",
        ),
    )
