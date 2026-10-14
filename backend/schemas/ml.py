"""Pydantic schemas for Machine Learning Pipeline Handoff Contract."""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class MLEvidenceTaskResponse(BaseModel):
    """Task contract exposed to ML workers for inference handoff."""
    evidence_id: uuid.UUID
    source_type: str
    source_provider: str | None = None
    media_type: str | None = None
    file_size_bytes: int | None = None
    sha256_checksum: str | None = None
    download_url: str
    captured_at: datetime | None = None
    ingested_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    incident_id: uuid.UUID | None = None
    road_segment_id: str | None = None
    acquisition_metadata: dict | None = None
    processing_status: str
    claimed_by: str | None = None
    claimed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MLClaimRequest(BaseModel):
    """Worker claiming pending evidence for processing."""
    worker_id: Annotated[str, Field(min_length=2, max_length=100, description="Unique worker instance identifier")]


class MLResultSubmissionRequest(BaseModel):
    """Worker submitting final inference result or failure."""
    worker_id: Annotated[str, Field(min_length=2, max_length=100)]
    status: Literal["COMPLETED", "FAILED"]
    model_detection_class: Annotated[str | None, Field(max_length=50, default=None)] = None
    model_confidence: Annotated[float | None, Field(ge=0.0, le=1.0, default=None)] = None
    model_metadata: dict | None = None
    error_message: Annotated[str | None, Field(max_length=2000, default=None)] = None


class MLPendingQueueResponse(BaseModel):
    """Collection of available evidence tasks for ML workers."""
    total_pending: int
    tasks: list[MLEvidenceTaskResponse]
