"""Pydantic schemas for Satellite Ingestion and Remote Sensing Metadata."""

import uuid
from datetime import datetime
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field


class SatelliteSceneIngestRequest(BaseModel):
    """Metadata for registering an external or uploaded satellite scene product."""
    scene_id: Annotated[str, Field(min_length=3, max_length=100, description="Unique scene ID (e.g. S2A_MSIL2A_20261014T...)")]
    provider: Annotated[str, Field(default="copernicus_sentinel2", max_length=50)]
    acquired_at: datetime | None = None
    cloud_cover_percent: Annotated[float | None, Field(ge=0.0, le=100.0, default=None)] = None
    resolution_m: Annotated[float | None, Field(ge=0.1, le=1000.0, default=None)] = None
    crs: Annotated[str | None, Field(max_length=50, default="EPSG:4326")] = "EPSG:4326"
    road_segment_id: Annotated[str | None, Field(max_length=64, default=None)] = None
    footprint_geojson: dict[str, Any] | None = None
    extra_metadata: dict[str, Any] | None = None


class SatelliteSyncRequest(BaseModel):
    """Parameters for triggering satellite catalog discovery for the corridor."""
    provider: Annotated[str, Field(default="copernicus_sentinel2", max_length=50)]
    max_cloud_cover_percent: Annotated[float, Field(ge=0.0, le=100.0, default=40.0)] = 40.0
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_scenes: Annotated[int, Field(ge=1, le=20, default=5)] = 5


class SatelliteIngestionLogResponse(BaseModel):
    """Audit entry for satellite scene ingestion."""
    id: uuid.UUID
    scene_id: str
    provider: str
    acquired_at: datetime | None = None
    cloud_cover_percent: float | None = None
    status: str
    evidence_id: uuid.UUID | None = None
    metadata_json: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SatelliteProviderInfo(BaseModel):
    """Details and operational status of configured satellite providers."""
    name: str
    provider_type: str
    is_live: bool
    status_note: str
    supported_resolutions_m: list[float]
    coverage_area: str
