"""FastAPI endpoints for Satellite Imagery Ingestion and Catalog Synchronization."""

import json
from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.evidence import EvidenceDetailResponse
from backend.schemas.satellite import (
    SatelliteIngestionLogResponse,
    SatelliteProviderInfo,
    SatelliteSceneIngestRequest,
    SatelliteSyncRequest,
)
from backend.services.evidence_service import to_evidence_detail_response
from backend.services.satellite.copernicus_adapter import get_satellite_adapter
from backend.services.satellite.satellite_service import SatelliteService

router = APIRouter(prefix="/satellite", tags=["Satellite Ingestion"])


@router.post("/ingest", response_model=EvidenceDetailResponse, status_code=status.HTTP_201_CREATED)
async def ingest_satellite_product(
    file: Annotated[UploadFile, File(...)],
    scene_id: Annotated[str, Form()],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker", "ml_service"]))],
    provider: Annotated[str, Form()] = "copernicus_sentinel2",
    cloud_cover_percent: Annotated[float | None, Form()] = None,
    resolution_m: Annotated[float | None, Form()] = None,
    crs: Annotated[str | None, Form()] = "EPSG:4326",
    road_segment_id: Annotated[str | None, Form()] = None,
    footprint_geojson: Annotated[str | None, Form()] = None,
    extra_metadata: Annotated[str | None, Form()] = None,
) -> EvidenceDetailResponse:
    """
    Registers and durably ingests a satellite raster/scene product and its acquisition provenance.
    Validates geospatial metadata, computes checksum, and registers evidence for ML hazard detection.
    """
    parsed_footprint = None
    if footprint_geojson:
        try:
            parsed_footprint = json.loads(footprint_geojson)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="footprint_geojson must be a valid GeoJSON object.",
            )

    parsed_extra = None
    if extra_metadata:
        try:
            parsed_extra = json.loads(extra_metadata)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="extra_metadata must be a valid JSON object.",
            )

    req = SatelliteSceneIngestRequest(
        scene_id=scene_id,
        provider=provider,
        cloud_cover_percent=cloud_cover_percent,
        resolution_m=resolution_m,
        crs=crs,
        road_segment_id=road_segment_id,
        footprint_geojson=parsed_footprint,
        extra_metadata=parsed_extra,
    )

    content = await file.read()
    service = SatelliteService(session)
    evidence = await service.ingest_satellite_product(
        file_content=content,
        original_filename=file.filename or f"{scene_id}.tif",
        payload=req,
        uploader_id=current_user.id,
    )
    return to_evidence_detail_response(evidence)


@router.post("/sync", response_model=list[EvidenceDetailResponse])
async def sync_satellite_scenes(
    payload: SatelliteSyncRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin", "service_worker"]))],
) -> list[EvidenceDetailResponse]:
    """
    Triggers catalog synchronization for the configured corridor bounding box
    using the selected satellite provider adapter.
    """
    service = SatelliteService(session)
    results = await service.sync_external_scenes(
        provider_name=payload.provider,
        max_cloud_cover=payload.max_cloud_cover_percent,
        max_scenes=payload.max_scenes,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return [to_evidence_detail_response(e) for e in results]


@router.get("/logs", response_model=list[SatelliteIngestionLogResponse])
async def list_satellite_logs(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SatelliteIngestionLogResponse]:
    """Lists audit logs of satellite scene ingestion attempts and deduplication records."""
    service = SatelliteService(session)
    logs = await service.list_logs(limit=limit, offset=offset)
    return [SatelliteIngestionLogResponse.model_validate(log) for log in logs]


@router.get("/providers", response_model=list[SatelliteProviderInfo])
async def list_satellite_providers(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SatelliteProviderInfo]:
    """Inspects configured satellite adapters, live API availability, and operational limitations."""
    copernicus = get_satellite_adapter("copernicus_sentinel2")
    mock_sentinel = get_satellite_adapter("mock_sentinel2")

    return [
        SatelliteProviderInfo(
            name=copernicus.name,
            provider_type="Copernicus Data Space Ecosystem (Sentinel-2 MSI)",
            is_live=copernicus.is_live,
            status_note=copernicus.status_note,
            supported_resolutions_m=[10.0, 20.0, 60.0],
            coverage_area="North Eastern Region / Global",
        ),
        SatelliteProviderInfo(
            name=mock_sentinel.name,
            provider_type="Synthetic Test Adapter",
            is_live=mock_sentinel.is_live,
            status_note=mock_sentinel.status_note,
            supported_resolutions_m=[10.0],
            coverage_area="Guwahati–Tawang Corridor (Configurable)",
        ),
    ]
