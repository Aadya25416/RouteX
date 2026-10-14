"""Pydantic schemas for Traffic Observations and Segment Metrics."""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class TrafficObservationResponse(BaseModel):
    """Segment-level traffic conditions derived from vehicle GPS tracks."""
    id: uuid.UUID
    road_segment_id: str
    window_start: datetime
    window_end: datetime
    sample_count: int
    avg_speed_kmh: float | None = None
    median_speed_kmh: float | None = None
    congestion_ratio: float | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA"]
    data_freshness_seconds: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrafficAggregateRequest(BaseModel):
    """Parameters for calculating traffic conditions over a recent time window."""
    window_minutes: Annotated[int, Field(ge=5, le=120, default=30)] = 30
    min_samples_for_high_confidence: Annotated[int, Field(ge=2, le=50, default=5)] = 5


class TrafficAggregationSummary(BaseModel):
    """Result of segment traffic calculation run."""
    segments_aggregated: int
    window_start: datetime
    window_end: datetime
    total_samples_analyzed: int
    high_confidence_segments: int
    insufficient_data_segments: int
