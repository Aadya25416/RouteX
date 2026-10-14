"""High-level service coordinating satellite scene ingestion, registration, and provenance."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_GeomFromGeoJSON
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import shape as shapely_shape

from backend.config import get_settings
from backend.models.incidents import IncidentEvidence
from backend.models.observations import SatelliteIngestionLog
from backend.schemas.satellite import SatelliteSceneIngestRequest
from backend.services.evidence_service import EvidenceService
from backend.services.satellite.base import SatelliteProviderAdapter
from backend.services.satellite.copernicus_adapter import get_satellite_adapter

logger = logging.getLogger(__name__)
settings = get_settings()


class SatelliteService:
    """Manages satellite scene ingestion, catalog synchronization, and audit logging."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.evidence_service = EvidenceService(session)

    async def ingest_satellite_product(
        self,
        file_content: bytes,
        original_filename: str,
        payload: SatelliteSceneIngestRequest,
        uploader_id: uuid.UUID | None = None,
    ) -> IncidentEvidence:
        """
        Registers and stores a satellite imagery product along with comprehensive acquisition metadata.
        Ensures idempotent deduplication via scene_id.
        """
        # 1. Deduplication check against SatelliteIngestionLog
        existing_log_res = await self.session.execute(
            select(SatelliteIngestionLog).where(SatelliteIngestionLog.scene_id == payload.scene_id)
        )
        existing_log = existing_log_res.scalars().first()
        if existing_log and existing_log.status == "SUCCESS" and existing_log.evidence_id:
            logger.info(f"Satellite scene '{payload.scene_id}' already ingested. Returning existing evidence.")
            return await self.evidence_service.get_evidence(existing_log.evidence_id)

        # 2. Plausibility validation for footprint
        footprint_wkt = None
        lat = None
        lon = None
        if payload.footprint_geojson:
            try:
                geom_shape = shapely_shape(payload.footprint_geojson)
                centroid = geom_shape.centroid
                lat = float(centroid.y)
                lon = float(centroid.x)
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                    raise ValueError(f"Centroid out of bounds: ({lat}, {lon})")
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid footprint_geojson geometry: {exc}",
                )

        # 3. Assemble normalized acquisition metadata
        acquisition_meta = {
            "scene_id": payload.scene_id,
            "provider": payload.provider,
            "cloud_cover_percent": payload.cloud_cover_percent,
            "resolution_m": payload.resolution_m,
            "crs": payload.crs,
            "footprint": payload.footprint_geojson,
            "extra": payload.extra_metadata or {},
        }

        # 4. Ingest into evidence store
        try:
            evidence = await self.evidence_service.ingest_evidence(
                file_content=file_content,
                original_filename=original_filename,
                source_type="SATELLITE",
                source_provider=payload.provider,
                road_segment_id=payload.road_segment_id,
                latitude=lat,
                longitude=lon,
                captured_at=payload.acquired_at or datetime.now(timezone.utc),
                acquisition_metadata=acquisition_meta,
                uploader_id=uploader_id,
            )

            # Record success in SatelliteIngestionLog
            ingest_log = SatelliteIngestionLog(
                id=uuid.uuid4(),
                scene_id=payload.scene_id,
                provider=payload.provider,
                acquired_at=payload.acquired_at,
                cloud_cover_percent=payload.cloud_cover_percent,
                status="SUCCESS",
                evidence_id=evidence.id,
                metadata_json=acquisition_meta,
            )
            self.session.add(ingest_log)
            await self.session.commit()
            return evidence

        except Exception as exc:
            logger.error(f"Failed to ingest satellite scene '{payload.scene_id}': {exc}")
            # Record failed attempt
            failure_log = SatelliteIngestionLog(
                id=uuid.uuid4(),
                scene_id=payload.scene_id,
                provider=payload.provider,
                acquired_at=payload.acquired_at,
                cloud_cover_percent=payload.cloud_cover_percent,
                status="FAILED",
                error_message=str(exc),
            )
            self.session.add(failure_log)
            await self.session.commit()
            raise

    async def sync_external_scenes(
        self,
        provider_name: str,
        max_cloud_cover: float = 40.0,
        max_scenes: int = 5,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[IncidentEvidence]:
        """
        Discovers scenes from provider adapter covering the configured corridor bounding box
        and ingests new unharvested scenes.
        """
        adapter = get_satellite_adapter(provider_name)
        bbox = settings.corridor_bbox
        now = datetime.now(timezone.utc)
        start = start_date or (now.replace(hour=0, minute=0, second=0))
        end = end_date or now

        scenes = await adapter.search_scenes(
            bbox=bbox,
            start_date=start,
            end_date=end,
            max_cloud_cover=max_cloud_cover,
            max_scenes=max_scenes,
        )

        ingested: list[IncidentEvidence] = []
        for s in scenes:
            scene_id = s["scene_id"]
            # Check already ingested
            chk = await self.session.execute(
                select(SatelliteIngestionLog).where(SatelliteIngestionLog.scene_id == scene_id)
            )
            if chk.scalars().first():
                continue

            try:
                content, filename, meta = await adapter.acquire_scene_product(scene_id)
                req = SatelliteSceneIngestRequest(
                    scene_id=scene_id,
                    provider=adapter.name,
                    acquired_at=datetime.fromisoformat(s["acquired_at"]) if isinstance(s.get("acquired_at"), str) else s.get("acquired_at"),
                    cloud_cover_percent=s.get("cloud_cover_percent"),
                    resolution_m=s.get("resolution_m"),
                    crs=s.get("crs", "EPSG:4326"),
                    footprint_geojson=s.get("footprint_geojson"),
                    extra_metadata=meta,
                )
                ev = await self.ingest_satellite_product(
                    file_content=content,
                    original_filename=filename,
                    payload=req,
                )
                ingested.append(ev)
            except Exception as exc:
                logger.warning(f"Error acquiring scene '{scene_id}': {exc}")

        return ingested

    async def list_logs(self, limit: int = 50, offset: int = 0) -> list[SatelliteIngestionLog]:
        res = await self.session.execute(
            select(SatelliteIngestionLog).order_by(SatelliteIngestionLog.created_at.desc()).limit(limit).offset(offset)
        )
        return list(res.scalars().all())
