"""Domain service for Unified Evidence Ingestion and ML Pipeline handoff."""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_MakeEnvelope, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.wkt import loads as wkt_loads
from geoalchemy2.shape import to_shape

from backend.config import get_settings
from backend.models.incidents import Incident, IncidentEvidence
from backend.models.roads import RoadSegment
from backend.models.users import User
from backend.schemas.evidence import EvidenceDetailResponse
from backend.schemas.ml import MLEvidenceTaskResponse
from backend.services.events import EventPublisher, record_audit_log
from backend.services.storage import compute_sha256, get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


def extract_evidence_coordinates(geom_val: object) -> tuple[float | None, float | None]:
    """Extracts (latitude, longitude) from a geometry element."""
    if geom_val is None:
        return None, None
    try:
        shape = to_shape(geom_val)
        return float(shape.y), float(shape.x)
    except Exception:
        s = str(geom_val)
        if "POINT" in s:
            wkt_part = s.split(";")[-1]
            shape = wkt_loads(wkt_part)
            return float(shape.y), float(shape.x)
        return None, None


class EvidenceService:
    """Manages raw evidence persistence, deduplication, retrieval, and ML handoff."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()
        self.storage = get_storage_service()

    async def ingest_evidence(
        self,
        file_content: bytes,
        original_filename: str,
        source_type: str = "FIELD_OFFICER",
        source_provider: str | None = None,
        incident_id: uuid.UUID | None = None,
        road_segment_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        captured_at: datetime | None = None,
        acquisition_metadata: dict | None = None,
        uploader_id: uuid.UUID | None = None,
        client_request_id: str | None = None,
    ) -> IncidentEvidence:
        """
        Validates, deduplicates, persists file into storage, and records normalized metadata.
        """
        file_size = len(file_content)
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file upload is not permitted.",
            )

        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size} bytes) exceeds limit ({settings.MAX_UPLOAD_SIZE_BYTES} bytes).",
            )

        checksum = compute_sha256(file_content)

        # Validate coordinates bounds if supplied
        if latitude is not None and not (-90.0 <= latitude <= 90.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid latitude {latitude}. Must be between -90 and 90.",
            )
        if longitude is not None and not (-180.0 <= longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid longitude {longitude}. Must be between -180 and 180.",
            )

        # Idempotency / Deduplication check:
        # Check if an evidence item with identical checksum already exists for this incident/source
        dedup_query = select(IncidentEvidence).where(IncidentEvidence.sha256_checksum == checksum)
        if incident_id:
            dedup_query = dedup_query.where(IncidentEvidence.incident_id == incident_id)
        else:
            dedup_query = dedup_query.where(IncidentEvidence.incident_id.is_(None))
        if source_provider:
            dedup_query = dedup_query.where(IncidentEvidence.source_provider == source_provider)
        existing_res = await self.session.execute(dedup_query)
        existing_evidence = existing_res.scalars().first()
        if existing_evidence:
            logger.info(f"Duplicate evidence upload detected for SHA-256 {checksum}. Returning existing record {existing_evidence.id}.")
            return existing_evidence

        # Check incident exists if specified
        if incident_id:
            inc = await self.session.get(Incident, incident_id)
            if not inc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Incident '{incident_id}' not found.",
                )
            if not road_segment_id and inc.road_segment_id:
                road_segment_id = inc.road_segment_id

        # Check road segment exists if specified
        if road_segment_id:
            seg = await self.session.get(RoadSegment, road_segment_id)
            if not seg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Road segment '{road_segment_id}' not found.",
                )

        # Persist to storage
        stored_name, file_url, stored_size, mime_type, file_hash = await self.storage.save_evidence_file(
            content=file_content,
            original_filename=original_filename,
            incident_id=incident_id,
        )

        # Create geometry if coordinates provided
        location_geom = None
        if latitude is not None and longitude is not None:
            location_geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        evidence_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        evidence = IncidentEvidence(
            id=evidence_id,
            incident_id=incident_id,
            road_segment_id=road_segment_id,
            uploader_id=uploader_id,
            file_url=file_url,
            original_filename=original_filename,
            stored_filename=stored_name,
            media_type=mime_type,
            file_size_bytes=stored_size,
            sha256_checksum=file_hash,
            source_type=source_type,
            source_provider=source_provider,
            location_geom=location_geom,
            acquisition_metadata=acquisition_metadata,
            validation_status="VALIDATED",
            captured_at=captured_at or now,
            processing_status="PENDING",
            created_at=now,
            updated_at=now,
        )

        self.session.add(evidence)

        record_audit_log(
            session=self.session,
            action="evidence_ingested",
            entity_type="incident_evidence",
            entity_id=str(evidence_id),
            actor_id=uploader_id,
            details={
                "source_type": source_type,
                "source_provider": source_provider,
                "stored_filename": stored_name,
                "sha256_checksum": file_hash,
                "file_size_bytes": stored_size,
                "incident_id": str(incident_id) if incident_id else None,
            },
        )

        await self.session.commit()
        await self.session.refresh(evidence)

        # Publish event for ML consumers & real-time notification
        await self.publisher.publish_event(
            event_type="evidence.ingested",
            entity_id=str(evidence.id),
            payload={
                "evidence_id": str(evidence.id),
                "incident_id": str(evidence.incident_id) if evidence.incident_id else None,
                "source_type": evidence.source_type,
                "sha256_checksum": evidence.sha256_checksum,
                "media_type": evidence.media_type,
                "file_size_bytes": evidence.file_size_bytes,
                "processing_status": evidence.processing_status,
            },
        )

        return evidence

    async def get_evidence(self, evidence_id: uuid.UUID) -> IncidentEvidence:
        """Retrieves an evidence record by ID."""
        evidence = await self.session.get(IncidentEvidence, evidence_id)
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence '{evidence_id}' not found.",
            )
        return evidence

    async def list_evidence(
        self,
        source_type: str | None = None,
        incident_id: uuid.UUID | None = None,
        road_segment_id: str | None = None,
        processing_status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_lat: float | None = None,
        min_lon: float | None = None,
        max_lat: float | None = None,
        max_lon: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[IncidentEvidence]]:
        """Filters and retrieves paginated evidence records."""
        query = select(IncidentEvidence)
        count_query = select(func.count(IncidentEvidence.id))

        if source_type:
            query = query.where(func.upper(IncidentEvidence.source_type) == source_type.upper())
            count_query = count_query.where(func.upper(IncidentEvidence.source_type) == source_type.upper())
        if incident_id:
            query = query.where(IncidentEvidence.incident_id == incident_id)
            count_query = count_query.where(IncidentEvidence.incident_id == incident_id)
        if road_segment_id:
            query = query.where(IncidentEvidence.road_segment_id == road_segment_id)
            count_query = count_query.where(IncidentEvidence.road_segment_id == road_segment_id)
        if processing_status:
            query = query.where(func.upper(IncidentEvidence.processing_status) == processing_status.upper())
            count_query = count_query.where(func.upper(IncidentEvidence.processing_status) == processing_status.upper())
        if start_date:
            query = query.where(IncidentEvidence.created_at >= start_date)
            count_query = count_query.where(IncidentEvidence.created_at >= start_date)
        if end_date:
            query = query.where(IncidentEvidence.created_at <= end_date)
            count_query = count_query.where(IncidentEvidence.created_at <= end_date)

        # Bounding box filter
        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            spatial_cond = or_(
                func.ST_Intersects(IncidentEvidence.location_geom, bbox_geom),
                func.ST_Intersects(IncidentEvidence.footprint_geom, bbox_geom),
            )
            query = query.where(spatial_cond)
            count_query = count_query.where(spatial_cond)

        total = (await self.session.execute(count_query)).scalar() or 0
        items_res = await self.session.execute(
            query.order_by(IncidentEvidence.created_at.desc()).limit(limit).offset(offset)
        )
        return total, list(items_res.scalars().all())

    # ==========================================
    # ML WORKER HANDOFF
    # ==========================================

    async def get_pending_tasks(
        self,
        limit: int = 20,
        source_type: str | None = None,
    ) -> list[IncidentEvidence]:
        """
        Discovers tasks waiting for ML processing:
        Includes status PENDING, plus stale IN_PROGRESS tasks whose lease expired.
        """
        lease_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.ML_CLAIM_TIMEOUT_MINUTES)
        condition = or_(
            IncidentEvidence.processing_status == "PENDING",
            (IncidentEvidence.processing_status == "IN_PROGRESS") & (IncidentEvidence.claimed_at < lease_cutoff),
        )

        query = select(IncidentEvidence).where(condition)
        if source_type:
            query = query.where(func.upper(IncidentEvidence.source_type) == source_type.upper())

        res = await self.session.execute(
            query.order_by(IncidentEvidence.created_at.desc()).limit(limit)
        )
        return list(res.scalars().all())

    async def claim_task(self, evidence_id: uuid.UUID, worker_id: str) -> IncidentEvidence:
        """
        Safely and atomically claims pending evidence for a worker instance.
        Prevents multiple workers from double processing the same record.
        """
        evidence = await self.session.get(IncidentEvidence, evidence_id, with_for_update=True)
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence '{evidence_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        lease_cutoff = now - timedelta(minutes=settings.ML_CLAIM_TIMEOUT_MINUTES)

        # If already IN_PROGRESS and lease has not expired: allow same worker (idempotent), reject other workers
        if evidence.processing_status == "IN_PROGRESS" and evidence.claimed_at and evidence.claimed_at >= lease_cutoff:
            if evidence.claimed_by == worker_id:
                # Same worker renewing/reclaiming its active task
                evidence.claimed_at = now
                evidence.updated_at = now
                await self.session.commit()
                await self.session.refresh(evidence)
                return evidence
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Evidence '{evidence_id}' is actively claimed by worker '{evidence.claimed_by}' until lease expires.",
                )

        if evidence.processing_status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evidence '{evidence_id}' is already COMPLETED and cannot be claimed.",
            )

        # Bounded retries: prevent permanently stuck tasks in infinite retry loop
        meta = dict(evidence.acquisition_metadata or {})
        attempts = int(meta.get("claim_attempts", 0)) + 1
        meta["claim_attempts"] = attempts
        evidence.acquisition_metadata = meta

        if attempts > 3:
            evidence.processing_status = "FAILED"
            evidence.processing_error = f"Maximum claim attempts ({attempts - 1}) exceeded. Evidence permanently marked FAILED."
            evidence.updated_at = now
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evidence '{evidence_id}' exceeded max processing attempts ({attempts - 1}) and was marked FAILED.",
            )

        evidence.processing_status = "IN_PROGRESS"
        evidence.claimed_by = worker_id
        evidence.claimed_at = now
        evidence.updated_at = now

        await self.session.commit()
        await self.session.refresh(evidence)

        logger.info(f"Worker '{worker_id}' successfully claimed evidence '{evidence_id}' (attempt {attempts}).")
        return evidence

    async def submit_task_result(
        self,
        evidence_id: uuid.UUID,
        worker_id: str,
        status_val: str,
        model_detection_class: str | None = None,
        model_confidence: float | None = None,
        model_metadata: dict | None = None,
        error_message: str | None = None,
    ) -> IncidentEvidence:
        """
        Records the inference result or failure reported by an ML worker.
        Idempotent: Repeated submissions for an already completed task return cleanly.
        """
        evidence = await self.session.get(IncidentEvidence, evidence_id, with_for_update=True)
        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence '{evidence_id}' not found.",
            )

        # Idempotency guard: If already completed with identical status, return cleanly
        if evidence.processing_status == "COMPLETED" and status_val == "COMPLETED":
            logger.info(f"Evidence '{evidence_id}' is already COMPLETED. Returning existing result idempotently.")
            return evidence

        now = datetime.now(timezone.utc)
        evidence.processing_status = status_val
        evidence.processed_at = now
        evidence.updated_at = now
        evidence.model_detection_class = model_detection_class
        evidence.model_confidence = model_confidence
        evidence.model_metadata = model_metadata
        evidence.processing_error = error_message

        record_audit_log(
            session=self.session,
            action="evidence_ml_processed",
            entity_type="incident_evidence",
            entity_id=str(evidence_id),
            details={
                "worker_id": worker_id,
                "status": status_val,
                "detection_class": model_detection_class,
                "confidence": model_confidence,
                "error": error_message,
            },
        )

        await self.session.commit()
        await self.session.refresh(evidence)

        # Notify via Redis stream
        await self.publisher.publish_event(
            event_type="evidence.ml_result",
            entity_id=str(evidence_id),
            payload={
                "evidence_id": str(evidence_id),
                "status": status_val,
                "detection_class": model_detection_class,
                "confidence": model_confidence,
            },
        )

        return evidence


def to_evidence_detail_response(e: IncidentEvidence) -> EvidenceDetailResponse:
    lat, lon = extract_evidence_coordinates(e.location_geom)
    download_url = f"/api/v1/evidence/{e.id}/download"
    return EvidenceDetailResponse(
        id=e.id,
        incident_id=e.incident_id,
        road_segment_id=e.road_segment_id,
        uploader_id=e.uploader_id,
        source_type=e.source_type,
        source_provider=e.source_provider,
        original_filename=e.original_filename,
        stored_filename=e.stored_filename,
        media_type=e.media_type,
        file_size_bytes=e.file_size_bytes,
        sha256_checksum=e.sha256_checksum,
        file_url=e.file_url,
        download_url=download_url,
        latitude=lat,
        longitude=lon,
        acquisition_metadata=e.acquisition_metadata,
        validation_status=e.validation_status,
        processing_status=e.processing_status,
        claimed_by=e.claimed_by,
        claimed_at=e.claimed_at,
        processed_at=e.processed_at,
        processing_error=e.processing_error,
        model_detection_class=e.model_detection_class,
        model_confidence=e.model_confidence,
        model_metadata=e.model_metadata,
        captured_at=e.captured_at,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def to_ml_task_response(e: IncidentEvidence) -> MLEvidenceTaskResponse:
    lat, lon = extract_evidence_coordinates(e.location_geom)
    download_url = f"/api/v1/ml/evidence/{e.id}/download"
    return MLEvidenceTaskResponse(
        evidence_id=e.id,
        source_type=e.source_type,
        source_provider=e.source_provider,
        media_type=e.media_type,
        file_size_bytes=e.file_size_bytes,
        sha256_checksum=e.sha256_checksum,
        download_url=download_url,
        captured_at=e.captured_at,
        ingested_at=e.created_at,
        latitude=lat,
        longitude=lon,
        incident_id=e.incident_id,
        road_segment_id=e.road_segment_id,
        acquisition_metadata=e.acquisition_metadata,
        processing_status=e.processing_status,
        claimed_by=e.claimed_by,
        claimed_at=e.claimed_at,
        model_detection_class=e.model_detection_class,
        model_confidence=e.model_confidence,
        model_metadata=e.model_metadata,
        processing_error=e.processing_error,
    )
