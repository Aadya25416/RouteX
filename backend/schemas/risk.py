"""Pydantic schemas for the Road Risk Scoring and Safety Assessment API."""

from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class RoadRiskItem(BaseModel):
    """Segment-level operational risk score, disruption probability, and provenance metadata."""
    road_segment_id: Annotated[str, Field(description="Canonical internal road segment ID")]
    road_name: Annotated[str | None, Field(default=None, description="Human-readable road name or corridor segment")]
    road_class: Annotated[str, Field(default="unclassified", description="OSM highway classification")]
    length_m: Annotated[float, Field(ge=0.0, description="Segment length in meters")]
    status: Annotated[
        str,
        Field(description="Current operational status: OPEN, AT_RISK, RESTRICTED, BLOCKED, or UNKNOWN"),
    ]
    safety_score: Annotated[
        float,
        Field(ge=0.0, le=100.0, description="0–100 safety score convention: 100 means safer, 0 means least safe"),
    ]
    disruption_probability: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="Disruption or blockage probability (0.0–1.0) from ML model"),
    ]
    score_confidence: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="Statistical confidence of the ML prediction"),
    ]
    score_type: Annotated[
        str,
        Field(default="ml_probabilistic", description="Score semantics: 'ml_probabilistic', 'authoritative_incident', 'heuristic_baseline', or 'unknown'"),
    ]
    model_name: Annotated[str | None, Field(default=None, description="Identifier of the executing model pipeline")]
    model_version: Annotated[str | None, Field(default=None, description="Exact version string of the model")]
    reason_codes: Annotated[list[str], Field(default_factory=list, description="Machine-readable contributing hazard factors")]
    is_stale: Annotated[bool, Field(default=False, description="True if prediction has surpassed its validity horizon")]
    is_unknown: Annotated[bool, Field(default=False, description="True if segment lacks current verified assessment")]
    score_updated_at: Annotated[datetime | None, Field(default=None, description="Timestamp when score was last evaluated")]
    score_valid_until: Annotated[datetime | None, Field(default=None, description="Expiration horizon for prediction")]
    coordinates: Annotated[list[list[float]] | None, Field(default=None, description="Segment LineString coordinates [[lon, lat], ...]")]

    model_config = ConfigDict(from_attributes=True)


class RoadRiskListResponse(BaseModel):
    """Paginated collection of road segment risk assessments."""
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[RoadRiskItem]


class RoadRiskEvaluationRequest(BaseModel):
    """Admin / dispatcher request to trigger explicit ML risk re-evaluation for a segment."""
    road_segment_id: str
