"""FastAPI endpoints for Field Incident Management (Phase 2)."""

import uuid
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope, ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.incidents import (
    Incident,
    IncidentEvidence,
    IncidentRoadAssociation,
    IncidentStatus,
)
from backend.models.users import User
from backend.schemas.incidents import (
    IncidentConfirmRequest,
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentEvidenceResponse,
    IncidentListResponse,
    IncidentRejectRequest,
    IncidentResolveRequest,
    IncidentReviewRequest,
    IncidentRoadAssociationResponse,
)
from backend.services.events import EventPublisher, record_audit_log
from backend.services.incident_service import IncidentService
from backend.services.storage import LocalStorageService, get_storage_service

router = APIRouter(prefix="/incidents", tags=["Incidents"])


from shapely.wkt import loads as wkt_loads
from geoalchemy2.shape import to_shape


def extract_coordinates(geom_val: object) -> tuple[float, float]:
    """Extracts (longitude, latitude) from geometry element or EWKT string."""
    if geom_val is None:
        return (0.0, 0.0)
    if isinstance(geom_val, str):
        wkt_part = geom_val.split(";")[-1]
        shape = wkt_loads(wkt_part)
        return (float(shape.x), float(shape.y))
    try:
        shape = to_shape(geom_val)
        return (float(shape.x), float(shape.y))
    except Exception:
        s = str(geom_val)
        if "POINT" in s:
            wkt_part = s.split(";")[-1]
            shape = wkt_loads(wkt_part)
            return (float(shape.x), float(shape.y))
        return (0.0, 0.0)


async def build_incident_detail_response(incident: Incident, session: AsyncSession) -> IncidentDetailResponse:
    """Helper formatting an Incident instance into IncidentDetailResponse with coordinates."""
    lon, lat = extract_coordinates(incident.geom)

    # Format road associations
    assocs = []
    for a in incident.road_associations:
        road_name = a.road_segment.name if a.road_segment else None
        road_class = a.road_segment.road_class if a.road_segment else None
        assocs.append(
            IncidentRoadAssociationResponse(
                id=a.id,
                road_segment_id=a.road_segment_id,
                association_type=a.association_type,
                assessed_impact=a.assessed_impact,
                distance_m=a.distance_m,
                road_name=road_name,
                road_class=road_class,
            )
        )

    # Format evidence items
    evidence = [
        IncidentEvidenceResponse(
            id=e.id,
            incident_id=e.incident_id,
            file_url=e.file_url,
            original_filename=e.original_filename,
            stored_filename=e.stored_filename,
            media_type=e.media_type,
            file_size_bytes=e.file_size_bytes,
            source_type=e.source_type,
            captured_at=e.captured_at,
            processing_status=e.processing_status,
            model_detection_class=e.model_detection_class,
            model_confidence=e.model_confidence,
            created_at=e.created_at,
        )
        for e in incident.evidence_items
    ]

    return IncidentDetailResponse(
        id=incident.id,
        client_report_id=incident.client_report_id,
        incident_type=incident.incident_type,
        severity=incident.severity,
        status=incident.status,
        description=incident.description,
        latitude=float(lat),
        longitude=float(lon),
        road_segment_id=incident.road_segment_id,
        source=incident.source,
        reporter_id=incident.reporter_id,
        observed_at=incident.observed_at,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        reviewed_at=incident.reviewed_at,
        reviewer_id=incident.reviewer_id,
        review_notes=incident.review_notes,
        resolved_at=incident.resolved_at,
        resolved_by=incident.resolved_by,
        resolution_notes=incident.resolution_notes,
        road_associations=assocs,
        evidence_items=evidence,
    )


# ---------------------------------------------------------
# 1. POST /api/v1/incidents — Create Incident
# ---------------------------------------------------------
@router.post("", response_model=IncidentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreateRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["field_officer", "dispatcher", "admin"]))],
) -> IncidentDetailResponse:
    """Submits a geotagged incident report with automatic PostGIS candidate road segment association."""
    service = IncidentService(session)
    incident, is_dup = await service.create_incident(
        incident_type=payload.incident_type.value,
        severity=payload.severity.value,
        latitude=payload.latitude,
        longitude=payload.longitude,
        observed_at=payload.observed_at,
        reporter_id=current_user.id,
        description=payload.description,
        client_report_id=payload.client_report_id,
        source=payload.source,
        search_radius_m=payload.search_radius_m,
    )
    return await build_incident_detail_response(incident, session)


# ---------------------------------------------------------
# 2. GET /api/v1/incidents — List Incidents
# ---------------------------------------------------------
@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    incident_type: Annotated[str | None, Query(alias="type")] = None,
    severity: Annotated[str | None, Query()] = None,
    min_observed_at: Annotated[datetime | None, Query()] = None,
    max_observed_at: Annotated[datetime | None, Query()] = None,
    min_lat: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    min_lon: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    max_lat: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    max_lon: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IncidentListResponse:
    """Lists field incidents with pagination and filters."""
    query = (
        select(Incident)
        .options(
            selectinload(Incident.road_associations).selectinload(IncidentRoadAssociation.road_segment),
            selectinload(Incident.evidence_items),
        )
    )
    count_query = select(func.count(Incident.id))

    if status_filter:
        query = query.where(Incident.status == status_filter.upper())
        count_query = count_query.where(Incident.status == status_filter.upper())

    if incident_type:
        query = query.where(Incident.incident_type == incident_type.upper())
        count_query = count_query.where(Incident.incident_type == incident_type.upper())

    if severity:
        query = query.where(Incident.severity == severity.upper())
        count_query = count_query.where(Incident.severity == severity.upper())

    if min_observed_at:
        query = query.where(Incident.observed_at >= min_observed_at)
        count_query = count_query.where(Incident.observed_at >= min_observed_at)

    if max_observed_at:
        query = query.where(Incident.observed_at <= max_observed_at)
        count_query = count_query.where(Incident.observed_at <= max_observed_at)

    if min_lat is not None and min_lon is not None and max_lat is not None and max_lon is not None:
        if min_lat >= max_lat or min_lon >= max_lon:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bounding box: min coordinates must be strictly less than max coordinates",
            )
        bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = query.where(ST_Intersects(Incident.geom, bbox_geom))
        count_query = count_query.where(ST_Intersects(Incident.geom, bbox_geom))

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    results = await session.execute(query)
    incidents = results.scalars().all()

    items = []
    for inc in incidents:
        items.append(await build_incident_detail_response(inc, session))

    return IncidentListResponse(total=total, limit=limit, offset=offset, items=items)


# ---------------------------------------------------------
# 3. GET /api/v1/incidents/{incident_id} — Detail
# ---------------------------------------------------------
@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> IncidentDetailResponse:
    """Retrieves full details for a single incident."""
    service = IncidentService(session)
    incident = await service.get_incident_by_id(incident_id)
    return await build_incident_detail_response(incident, session)


# ---------------------------------------------------------
# 4. POST /api/v1/incidents/{incident_id}/review — Review
# ---------------------------------------------------------
@router.post("/{incident_id}/review", response_model=IncidentDetailResponse)
async def review_incident(
    incident_id: uuid.UUID,
    payload: IncidentReviewRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> IncidentDetailResponse:
    """Authorized dispatcher or admin marks an incident as UNDER_REVIEW."""
    service = IncidentService(session)
    updated = await service.review_incident(
        incident_id=incident_id,
        reviewer_id=current_user.id,
        review_notes=payload.review_notes,
    )
    return await build_incident_detail_response(updated, session)


# ---------------------------------------------------------
# 5. POST /api/v1/incidents/{incident_id}/confirm — Confirm
# ---------------------------------------------------------
@router.post("/{incident_id}/confirm", response_model=IncidentDetailResponse)
async def confirm_incident(
    incident_id: uuid.UUID,
    payload: IncidentConfirmRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> IncidentDetailResponse:
    """Authorized dispatcher or admin confirms incident and updates affected road segment operational status."""
    service = IncidentService(session)
    road_impacts = [item.model_dump() for item in payload.road_impacts]
    updated = await service.confirm_incident(
        incident_id=incident_id,
        reviewer_id=current_user.id,
        road_impacts=road_impacts,
        review_notes=payload.review_notes,
    )
    return await build_incident_detail_response(updated, session)


# ---------------------------------------------------------
# 6. POST /api/v1/incidents/{incident_id}/reject — Reject
# ---------------------------------------------------------
@router.post("/{incident_id}/reject", response_model=IncidentDetailResponse)
async def reject_incident(
    incident_id: uuid.UUID,
    payload: IncidentRejectRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> IncidentDetailResponse:
    """Authorized dispatcher or admin rejects an incident with a required reason."""
    service = IncidentService(session)
    updated = await service.reject_incident(
        incident_id=incident_id,
        reviewer_id=current_user.id,
        rejection_reason=payload.rejection_reason,
    )
    return await build_incident_detail_response(updated, session)


# ---------------------------------------------------------
# 7. POST /api/v1/incidents/{incident_id}/resolve — Resolve
# ---------------------------------------------------------
@router.post("/{incident_id}/resolve", response_model=IncidentDetailResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    payload: IncidentResolveRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["dispatcher", "admin"]))],
) -> IncidentDetailResponse:
    """Authorized dispatcher or admin resolves an incident. Retains UNKNOWN road state unless verified clearance."""
    service = IncidentService(session)
    updated = await service.resolve_incident(
        incident_id=incident_id,
        resolved_by=current_user.id,
        resolution_notes=payload.resolution_notes,
        verified_clearance=payload.verified_clearance,
    )
    return await build_incident_detail_response(updated, session)


# ---------------------------------------------------------
# 8. POST /api/v1/incidents/{incident_id}/evidence — Upload
# ---------------------------------------------------------
@router.post(
    "/{incident_id}/evidence",
    response_model=IncidentEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    incident_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["field_officer", "dispatcher", "admin"]))],
    file: Annotated[UploadFile, File(...)],
    captured_at: Annotated[datetime | None, Query()] = None,
) -> IncidentEvidenceResponse:
    """Uploads photographic evidence for an incident. Validates file header magic bytes and size."""
    # Ensure incident exists
    service = IncidentService(session)
    incident = await service.get_incident_by_id(incident_id)

    storage = get_storage_service()
    content = await file.read()
    stored_name, file_url, file_size, mime = await storage.save_evidence_file(
        content=content,
        original_filename=file.filename or "photo.jpg",
        incident_id=incident.id,
    )

    evidence_id = uuid.uuid4()
    evidence = IncidentEvidence(
        id=evidence_id,
        incident_id=incident.id,
        file_url=file_url,
        original_filename=file.filename or "photo.jpg",
        stored_filename=stored_name,
        media_type=mime,
        file_size_bytes=file_size,
        source_type="field_photo",
        captured_at=captured_at,
        processing_status="PENDING",
    )
    session.add(evidence)

    record_audit_log(
        session=session,
        action="incident_evidence_uploaded",
        entity_type="incident_evidence",
        entity_id=str(evidence_id),
        actor_id=current_user.id,
        details={
            "incident_id": str(incident.id),
            "stored_filename": stored_name,
            "media_type": mime,
            "size_bytes": file_size,
        },
    )

    await session.commit()
    await session.refresh(evidence)

    # Publish event
    publisher = EventPublisher()
    await publisher.publish_event(
        event_type="incident.evidence_uploaded",
        entity_id=str(evidence.id),
        payload={
            "evidence_id": str(evidence.id),
            "incident_id": str(incident.id),
            "media_type": mime,
            "file_size_bytes": file_size,
            "uploaded_by": str(current_user.id),
        },
    )

    return IncidentEvidenceResponse.model_validate(evidence)


# ---------------------------------------------------------
# 9. GET /api/v1/incidents/{incident_id}/evidence — List evidence
# ---------------------------------------------------------
@router.get("/{incident_id}/evidence", response_model=list[IncidentEvidenceResponse])
async def list_incident_evidence(
    incident_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[IncidentEvidenceResponse]:
    """Lists evidence metadata for an incident."""
    service = IncidentService(session)
    incident = await service.get_incident_by_id(incident_id)
    return [IncidentEvidenceResponse.model_validate(e) for e in incident.evidence_items]


# ---------------------------------------------------------
# 10. GET /api/v1/incidents/{incident_id}/evidence/{evidence_id_or_file}/download — Download
# ---------------------------------------------------------
@router.get("/{incident_id}/evidence/{evidence_ref}/download")
async def download_evidence(
    incident_id: uuid.UUID,
    evidence_ref: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Protected evidence retrieval endpoint requiring authentication."""
    # Lookup by evidence UUID or stored_filename
    evidence_uuid = None
    try:
        evidence_uuid = uuid.UUID(evidence_ref)
    except ValueError:
        pass

    query = select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id)
    if evidence_uuid:
        query = query.where(IncidentEvidence.id == evidence_uuid)
    else:
        query = query.where(IncidentEvidence.stored_filename == evidence_ref)

    res = await session.execute(query)
    evidence = res.scalar_one_or_none()
    if not evidence or not evidence.stored_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence '{evidence_ref}' for incident '{incident_id}' not found.",
        )

    storage = get_storage_service()
    content, mime = await storage.get_evidence_file(evidence.stored_filename)

    safe_orig_filename = evidence.original_filename or "evidence.jpg"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{safe_orig_filename}"'},
    )
