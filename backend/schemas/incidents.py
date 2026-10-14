"""Pydantic schemas for Incident Management API."""

import uuid
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

from backend.models.incidents import (
    AssessedImpact,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentType,
)


class IncidentCreateRequest(BaseModel):
    """Schema for submitting a field incident."""
    incident_type: IncidentType
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="Latitude in WGS84")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="Longitude in WGS84")]
    description: Annotated[str | None, Field(max_length=2000, default=None)]
    observed_at: datetime
    client_report_id: Annotated[str | None, Field(max_length=64, default=None, description="Client idempotency key")]
    source: str = IncidentSource.FIELD_REPORT.value
    search_radius_m: Annotated[float | None, Field(ge=10.0, le=5000.0, default=None)]


class RoadImpactInput(BaseModel):
    """Assessed impact for an associated road segment during confirmation."""
    road_segment_id: str
    assessed_impact: AssessedImpact = AssessedImpact.BLOCKED


class IncidentReviewRequest(BaseModel):
    """Request schema for moving an incident to review."""
    review_notes: str | None = None


class IncidentConfirmRequest(BaseModel):
    """Request schema for confirming an incident with verified impacts."""
    review_notes: str | None = None
    road_impacts: list[RoadImpactInput] = Field(default_factory=list)


class IncidentRejectRequest(BaseModel):
    """Request schema for rejecting an incident."""
    rejection_reason: Annotated[str, Field(min_length=3, max_length=1000)]


class IncidentResolveRequest(BaseModel):
    """Request schema for resolving an incident."""
    resolution_notes: Annotated[str, Field(min_length=3, max_length=1000)]
    verified_clearance: bool = False


class IncidentEvidenceResponse(BaseModel):
    """Metadata response for uploaded evidence."""
    id: uuid.UUID
    incident_id: uuid.UUID | None = None
    file_url: str
    original_filename: str | None = None
    stored_filename: str | None = None
    media_type: str | None = None
    file_size_bytes: int | None = None
    sha256_checksum: str | None = None
    source_type: str
    source_provider: str | None = None
    uploader_id: uuid.UUID | None = None
    road_segment_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    acquisition_metadata: dict | None = None
    validation_status: str = "VALIDATED"
    captured_at: datetime | None = None
    processing_status: str
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    processing_error: str | None = None
    model_detection_class: str | None = None
    model_confidence: float | None = None
    model_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IncidentRoadAssociationResponse(BaseModel):
    """Road segment association details."""
    id: uuid.UUID
    road_segment_id: str
    association_type: str
    assessed_impact: str | None = None
    distance_m: float | None = None
    road_name: str | None = None
    road_class: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IncidentDetailResponse(BaseModel):
    """Comprehensive incident response model."""
    id: uuid.UUID
    client_report_id: str | None = None
    incident_type: str
    severity: str
    status: str
    description: str | None = None
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    source: str
    reporter_id: uuid.UUID | None = None
    observed_at: datetime
    created_at: datetime
    updated_at: datetime

    reviewed_at: datetime | None = None
    reviewer_id: uuid.UUID | None = None
    review_notes: str | None = None

    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
    resolution_notes: str | None = None

    road_associations: list[IncidentRoadAssociationResponse] = Field(default_factory=list)
    evidence_items: list[IncidentEvidenceResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""
    total: int
    limit: int
    offset: int
    items: list[IncidentDetailResponse]
