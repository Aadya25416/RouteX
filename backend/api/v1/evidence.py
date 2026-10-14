"""Unified raw evidence ingestion endpoints for field-officer and satellite sources."""

import json
import uuid
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.evidence import EvidenceDetailResponse, EvidenceListResponse
from backend.services.evidence_service import EvidenceService, to_evidence_detail_response
from backend.services.storage import get_storage_service

router = APIRouter(prefix="/evidence", tags=["Evidence Ingestion"])


@router.post("/upload", response_model=EvidenceDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["field_officer", "dispatcher", "admin", "service_worker", "ml_service", "driver"]))],
    source_type: Annotated[str, Form()] = "FIELD_OFFICER",
    source_provider: Annotated[str | None, Form()] = None,
    incident_id: Annotated[uuid.UUID | None, Form()] = None,
    road_segment_id: Annotated[str | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    captured_at: Annotated[datetime | None, Form()] = None,
    acquisition_metadata: Annotated[str | None, Form()] = None,
    client_request_id: Annotated[str | None, Form()] = None,
) -> EvidenceDetailResponse:
    """
    Ingests and durably persists raw photographic or satellite evidence.
    Validates file signatures, generates SHA-256 checksums, and registers metadata for ML consumption.
    """
    parsed_metadata = None
    if acquisition_metadata:
        try:
            parsed_metadata = json.loads(acquisition_metadata)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="acquisition_metadata must be valid JSON string.",
            )

    content = await file.read()
    service = EvidenceService(session)
    evidence = await service.ingest_evidence(
        file_content=content,
        original_filename=file.filename or "evidence.jpg",
        source_type=source_type,
        source_provider=source_provider,
        incident_id=incident_id,
        road_segment_id=road_segment_id,
        latitude=latitude,
        longitude=longitude,
        captured_at=captured_at,
        acquisition_metadata=parsed_metadata,
        uploader_id=current_user.id,
        client_request_id=client_request_id,
    )

    return to_evidence_detail_response(evidence)


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    source_type: Annotated[str | None, Query(description="Filter by FIELD_OFFICER, SATELLITE, etc.")] = None,
    incident_id: Annotated[uuid.UUID | None, Query()] = None,
    road_segment_id: Annotated[str | None, Query()] = None,
    processing_status: Annotated[str | None, Query(description="PENDING, IN_PROGRESS, COMPLETED, FAILED")] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    min_lat: Annotated[float | None, Query()] = None,
    min_lon: Annotated[float | None, Query()] = None,
    max_lat: Annotated[float | None, Query()] = None,
    max_lon: Annotated[float | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceListResponse:
    """Retrieves paginated evidence records with source, date, processing, and spatial bounds filtering."""
    service = EvidenceService(session)
    total, items = await service.list_evidence(
        source_type=source_type,
        incident_id=incident_id,
        road_segment_id=road_segment_id,
        processing_status=processing_status,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )
    return EvidenceListResponse(
        total=total,
        items=[to_evidence_detail_response(e) for e in items],
    )


@router.get("/{evidence_id}", response_model=EvidenceDetailResponse)
async def get_evidence(
    evidence_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceDetailResponse:
    """Retrieves an evidence record and its associated acquisition metadata."""
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id)
    return to_evidence_detail_response(evidence)


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Secure endpoint for downloading raw evidence binary file."""
    service = EvidenceService(session)
    evidence = await service.get_evidence(evidence_id)

    if not evidence.stored_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence binary reference for '{evidence_id}' not found.",
        )

    storage = get_storage_service()
    content, mime = await storage.get_evidence_file(evidence.stored_filename)

    safe_filename = evidence.original_filename or "evidence.jpg"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
    )
