"""Pydantic schemas for Unified Evidence Ingestion."""

import uuid
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field


class EvidenceUploadMetadata(BaseModel):
    """Metadata fields submitted alongside uploaded raw evidence."""
    source_type: Annotated[str, Field(default="FIELD_OFFICER", max_length=50, description="FIELD_OFFICER, SATELLITE, field_photo, satellite_scene")]
    source_provider: Annotated[str | None, Field(max_length=100, default=None, description="Camera ID, satellite provider, sensor name")]
    incident_id: uuid.UUID | None = None
    road_segment_id: Annotated[str | None, Field(max_length=64, default=None)] = None
    latitude: Annotated[float | None, Field(ge=-90.0, le=90.0, default=None)] = None
    longitude: Annotated[float | None, Field(ge=-180.0, le=180.0, default=None)] = None
    captured_at: datetime | None = None
    acquisition_metadata: dict | None = None
    client_request_id: Annotated[str | None, Field(max_length=100, default=None, description="Idempotency key")]


class EvidenceDetailResponse(BaseModel):
    """Full metadata for persisted evidence."""
    id: uuid.UUID
    incident_id: uuid.UUID | None = None
    road_segment_id: str | None = None
    uploader_id: uuid.UUID | None = None
    source_type: str
    source_provider: str | None = None
    original_filename: str | None = None
    stored_filename: str | None = None
    media_type: str | None = None
    file_size_bytes: int | None = None
    sha256_checksum: str | None = None
    file_url: str
    download_url: str
    latitude: float | None = None
    longitude: float | None = None
    acquisition_metadata: dict | None = None
    validation_status: str
    processing_status: str
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    processing_error: str | None = None
    model_detection_class: str | None = None
    model_confidence: float | None = None
    model_metadata: dict | None = None
    captured_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceListResponse(BaseModel):
    """Paginated list of evidence records."""
    total: int
    items: list[EvidenceDetailResponse]
