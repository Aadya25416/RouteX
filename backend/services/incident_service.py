"""Incident management service implementing lifecycle workflows and road state aggregation."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.audit import AuditLog
from backend.models.incidents import (
    AssessedImpact,
    AssociationType,
    Incident,
    IncidentEvidence,
    IncidentRoadAssociation,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentType,
)
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.services.events import EventPublisher, record_audit_log

logger = logging.getLogger(__name__)
settings = get_settings()


class IncidentService:
    """Core domain service for incident reporting, validation, lifecycle, and road state updates."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()

    async def create_incident(
        self,
        incident_type: str,
        severity: str,
        latitude: float,
        longitude: float,
        observed_at: datetime,
        reporter_id: uuid.UUID | None,
        description: str | None = None,
        client_report_id: str | None = None,
        source: str = IncidentSource.FIELD_REPORT.value,
        search_radius_m: float | None = None,
    ) -> tuple[Incident, bool]:
        """
        Creates a new incident with PostGIS spatial road matching and idempotency.
        Returns (incident, is_existing_duplicate).
        """
        # 1. Idempotency check: if client_report_id already exists, return existing record
        if client_report_id:
            existing_query = (
                select(Incident)
                .options(
                    selectinload(Incident.road_associations).selectinload(IncidentRoadAssociation.road_segment),
                    selectinload(Incident.evidence_items),
                )
                .where(Incident.client_report_id == client_report_id)
            )
            res = await self.session.execute(existing_query)
            existing_incident = res.scalar_one_or_none()
            if existing_incident:
                logger.info(f"Duplicate client_report_id '{client_report_id}' detected. Returning existing incident {existing_incident.id}.")
                return existing_incident, True

        # 2. Coordinate range validation
        if not (-90.0 <= latitude <= 90.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid latitude: {latitude}. Must be between -90 and 90.",
            )
        if not (-180.0 <= longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid longitude: {longitude}. Must be between -180 and 180.",
            )

        # 3. PostGIS Geometry creation
        point_ewkt = f"SRID=4326;POINT({longitude} {latitude})"
        point_geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        # 4. Nearby candidate road segment matching using ST_DWithin and geography distance
        radius = search_radius_m or settings.INCIDENT_ROAD_MATCH_RADIUS_M
        spatial_query = (
            select(
                RoadSegment,
                ST_Distance(
                    cast(RoadSegment.geom, Geography),
                    cast(point_geom, Geography),
                ).label("distance_meters"),
            )
            .where(
                ST_DWithin(
                    cast(RoadSegment.geom, Geography),
                    cast(point_geom, Geography),
                    radius,
                )
            )
            .order_by("distance_meters")
            .limit(10)
        )

        candidates_res = await self.session.execute(spatial_query)
        candidates = candidates_res.all()

        primary_segment_id: str | None = candidates[0][0].id if candidates else None

        # 5. Persist Incident
        incident = Incident(
            id=uuid.uuid4(),
            incident_type=incident_type,
            severity=severity,
            description=description,
            geom=point_ewkt,
            road_segment_id=primary_segment_id,
            status=IncidentStatus.SUBMITTED.value,
            source=source,
            reporter_id=reporter_id,
            client_report_id=client_report_id,
            observed_at=observed_at,
        )
        self.session.add(incident)
        await self.session.flush()

        # 6. Associate candidate road segments with SUGGESTED type
        for segment, dist in candidates:
            assoc = IncidentRoadAssociation(
                id=uuid.uuid4(),
                incident_id=incident.id,
                road_segment_id=segment.id,
                association_type=AssociationType.SUGGESTED.value,
                assessed_impact=None,  # Not verified yet
                distance_m=round(float(dist), 2),
            )
            self.session.add(assoc)

        # 7. Record audit log
        record_audit_log(
            session=self.session,
            action="incident_submitted",
            entity_type="incident",
            entity_id=str(incident.id),
            actor_id=reporter_id,
            details={
                "client_report_id": client_report_id,
                "type": incident_type,
                "severity": severity,
                "candidate_segments_count": len(candidates),
                "primary_segment_id": primary_segment_id,
            },
        )

        await self.session.commit()

        # 8. Reload with relationships
        incident_reloaded = await self.get_incident_by_id(incident.id)

        # 9. Emit event
        await self.publisher.publish_event(
            event_type="incident.created",
            entity_id=str(incident.id),
            payload={
                "incident_id": str(incident.id),
                "type": incident_type,
                "severity": severity,
                "latitude": latitude,
                "longitude": longitude,
                "reporter_id": str(reporter_id) if reporter_id else None,
                "candidate_road_ids": [c[0].id for c in candidates],
            },
        )
        # 10. Generate alert for critical/high reported incident
        if severity and severity.upper() in ("CRITICAL", "HIGH"):
            try:
                from backend.services.alert_service import AlertService
                alert_service = AlertService(session=self.session, event_publisher=self.publisher)
                await alert_service.create_alert(
                    event_type="incident.created",
                    severity=severity.lower(),
                    message=f"High-priority incident ({incident_type}) reported: {description or 'Potential corridor hazard'}.",
                    recipient_role="dispatcher",
                    entity_type="incident",
                    entity_id=str(incident.id),
                    details={"incident_id": str(incident.id), "type": incident_type, "severity": severity},
                    dedup_key=f"alert:incident_created:{incident.id}",
                )
            except Exception as alert_exc:
                logger.warning(f"Failed to create alert for new critical incident {incident.id}: {alert_exc}")

        return incident_reloaded, False

    async def get_incident_by_id(self, incident_id: uuid.UUID) -> Incident:
        """Retrieves a single incident by ID with road associations and evidence."""
        query = (
            select(Incident)
            .options(
                selectinload(Incident.road_associations).selectinload(IncidentRoadAssociation.road_segment),
                selectinload(Incident.evidence_items),
            )
            .where(Incident.id == incident_id)
        )
        res = await self.session.execute(query)
        incident = res.scalar_one_or_none()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with id '{incident_id}' not found.",
            )
        return incident

    async def review_incident(
        self,
        incident_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        review_notes: str | None = None,
    ) -> Incident:
        """Transitions an incident into UNDER_REVIEW."""
        incident = await self.get_incident_by_id(incident_id)

        # Permitted transitions: SUBMITTED -> UNDER_REVIEW or updating existing UNDER_REVIEW
        if incident.status not in [IncidentStatus.SUBMITTED.value, IncidentStatus.UNDER_REVIEW.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot review incident with status '{incident.status}'. Only SUBMITTED or UNDER_REVIEW allowed.",
            )

        incident.status = IncidentStatus.UNDER_REVIEW.value
        incident.reviewer_id = reviewer_id
        incident.reviewed_at = datetime.now(timezone.utc)
        if review_notes:
            incident.review_notes = review_notes

        record_audit_log(
            session=self.session,
            action="incident_reviewed",
            entity_type="incident",
            entity_id=str(incident.id),
            actor_id=reviewer_id,
            details={"status": incident.status, "notes": review_notes},
        )

        await self.session.commit()
        return await self.get_incident_by_id(incident_id)

    async def confirm_incident(
        self,
        incident_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        road_impacts: list[dict[str, str]],
        review_notes: str | None = None,
    ) -> Incident:
        """
        Confirms an incident, verifies road segment associations and impacts,
        and recalculates the affected road segments' operational states.
        """
        incident = await self.get_incident_by_id(incident_id)

        # Permitted transitions: SUBMITTED -> CONFIRMED, UNDER_REVIEW -> CONFIRMED
        if incident.status not in [IncidentStatus.SUBMITTED.value, IncidentStatus.UNDER_REVIEW.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm incident in state '{incident.status}'. Must be SUBMITTED or UNDER_REVIEW.",
            )

        if not road_impacts:
            # If reviewer provided no explicit list, verify existing candidates if any with default impact
            if incident.road_associations:
                default_impact = AssessedImpact.BLOCKED.value if incident.severity in [IncidentSeverity.HIGH.value, IncidentSeverity.CRITICAL.value] else AssessedImpact.AT_RISK.value
                for assoc in incident.road_associations:
                    assoc.association_type = AssociationType.VERIFIED.value
                    assoc.assessed_impact = default_impact
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot confirm incident without at least one verified road segment association.",
                )
        else:
            # Reconcile verified road associations
            # Map existing associations by road_segment_id
            existing_assocs = {a.road_segment_id: a for a in incident.road_associations}
            submitted_segment_ids = set()

            for item in road_impacts:
                seg_id = item["road_segment_id"]
                impact = item.get("assessed_impact", AssessedImpact.BLOCKED.value).upper()
                if impact not in [e.value for e in AssessedImpact]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid assessed impact '{impact}'. Allowed: {[e.value for e in AssessedImpact]}",
                    )

                # Verify segment exists
                seg = await self.session.get(RoadSegment, seg_id)
                if not seg:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Road segment '{seg_id}' not found.",
                    )

                submitted_segment_ids.add(seg_id)
                if seg_id in existing_assocs:
                    existing_assocs[seg_id].association_type = AssociationType.VERIFIED.value
                    existing_assocs[seg_id].assessed_impact = impact
                else:
                    new_assoc = IncidentRoadAssociation(
                        id=uuid.uuid4(),
                        incident_id=incident.id,
                        road_segment_id=seg_id,
                        association_type=AssociationType.VERIFIED.value,
                        assessed_impact=impact,
                        distance_m=None,
                    )
                    self.session.add(new_assoc)
                    incident.road_associations.append(new_assoc)

            # Remove any non-verified suggested associations that official removed
            for seg_id, assoc in existing_assocs.items():
                if seg_id not in submitted_segment_ids:
                    await self.session.delete(assoc)
                    if assoc in incident.road_associations:
                        incident.road_associations.remove(assoc)

        # Update incident metadata
        incident.status = IncidentStatus.CONFIRMED.value
        incident.reviewer_id = reviewer_id
        incident.reviewed_at = datetime.now(timezone.utc)
        incident.verified_at = incident.reviewed_at
        incident.verified_by = reviewer_id
        if review_notes:
            incident.review_notes = review_notes

        await self.session.flush()

        # Recalculate affected road states
        if road_impacts:
            affected_segment_ids = list(submitted_segment_ids)
        else:
            affected_segment_ids = [
                a.road_segment_id for a in incident.road_associations
                if a.association_type == AssociationType.VERIFIED.value
            ]
        status_changes = []
        for seg_id in affected_segment_ids:
            change = await self.recalculate_road_segment_state(seg_id)
            if change:
                status_changes.append(change)

        # Record audit entry
        record_audit_log(
            session=self.session,
            action="incident_confirmed",
            entity_type="incident",
            entity_id=str(incident.id),
            actor_id=reviewer_id,
            details={
                "status": incident.status,
                "affected_segments": affected_segment_ids,
                "notes": review_notes,
            },
        )

        await self.session.commit()

        # Emit events
        await self.publisher.publish_event(
            event_type="incident.confirmed",
            entity_id=str(incident.id),
            payload={
                "incident_id": str(incident.id),
                "reviewer_id": str(reviewer_id),
                "affected_segments": affected_segment_ids,
            },
        )
        for seg_id, old_st, new_st in status_changes:
            await self.publisher.publish_event(
                event_type="road.status_changed",
                entity_id=seg_id,
                payload={
                    "road_segment_id": seg_id,
                    "previous_status": old_st,
                    "new_status": new_st,
                    "incident_id": str(incident.id),
                },
            )

        # Trigger disruption evaluation for active trips
        blocked_seg_ids = [seg_id for seg_id, old_st, new_st in status_changes if new_st == RoadStatus.BLOCKED.value]
        if blocked_seg_ids:
            try:
                from backend.services.logistics_service import LogisticsService
                logistics_service = LogisticsService(session=self.session, event_publisher=self.publisher)
                await logistics_service.check_and_reroute_disrupted_trips(blocked_seg_ids, actor_id=reviewer_id)
            except Exception as exc:
                logger.error(f"Error evaluating disrupted trips during incident confirmation: {exc}")

        # Generate alert for confirmed critical incident or road blockage
        if blocked_seg_ids or (incident.severity and incident.severity.upper() in ("CRITICAL", "HIGH")):
            try:
                from backend.services.alert_service import AlertService
                alert_service = AlertService(session=self.session, event_publisher=self.publisher)
                severity_val = "critical" if blocked_seg_ids or incident.severity == "CRITICAL" else "high"
                msg = (
                    f"Incident #{str(incident.id)[:8]} confirmed. Road segment(s) {', '.join(blocked_seg_ids)} are BLOCKED."
                    if blocked_seg_ids
                    else f"Incident #{str(incident.id)[:8]} ({incident.incident_type}) confirmed with severity {incident.severity}."
                )
                await alert_service.create_alert(
                    event_type="road.blockage" if blocked_seg_ids else "incident.confirmed",
                    severity=severity_val,
                    message=msg,
                    recipient_role="dispatcher",
                    entity_type="incident",
                    entity_id=str(incident.id),
                    details={
                        "incident_id": str(incident.id),
                        "blocked_segments": blocked_seg_ids,
                        "severity": incident.severity,
                        "status": incident.status,
                    },
                    dedup_key=f"alert:incident_confirmed:{incident.id}",
                )
            except Exception as alert_exc:
                logger.warning(f"Failed to create alert for confirmed incident {incident.id}: {alert_exc}")

        return await self.get_incident_by_id(incident_id)

    async def reject_incident(
        self,
        incident_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        rejection_reason: str,
    ) -> Incident:
        """Rejects an incident with an explicit mandatory reason and recalculates road state."""
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required when rejecting an incident.",
            )

        incident = await self.get_incident_by_id(incident_id)

        # Permitted transitions: SUBMITTED -> REJECTED, UNDER_REVIEW -> REJECTED
        if incident.status not in [IncidentStatus.SUBMITTED.value, IncidentStatus.UNDER_REVIEW.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject incident in state '{incident.status}'. Must be SUBMITTED or UNDER_REVIEW.",
            )

        previous_status = incident.status
        incident.status = IncidentStatus.REJECTED.value
        incident.reviewer_id = reviewer_id
        incident.reviewed_at = datetime.now(timezone.utc)
        incident.review_notes = rejection_reason.strip()

        # If it had verified associations, recalculate those road states
        affected_segment_ids = [
            a.road_segment_id for a in incident.road_associations
            if a.association_type == AssociationType.VERIFIED.value
        ]

        await self.session.flush()

        status_changes = []
        for seg_id in affected_segment_ids:
            change = await self.recalculate_road_segment_state(seg_id)
            if change:
                status_changes.append(change)

        record_audit_log(
            session=self.session,
            action="incident_rejected",
            entity_type="incident",
            entity_id=str(incident.id),
            actor_id=reviewer_id,
            details={
                "previous_status": previous_status,
                "rejection_reason": rejection_reason,
            },
        )

        await self.session.commit()

        await self.publisher.publish_event(
            event_type="incident.rejected",
            entity_id=str(incident.id),
            payload={
                "incident_id": str(incident.id),
                "reviewer_id": str(reviewer_id),
                "reason": rejection_reason,
            },
        )
        for seg_id, old_st, new_st in status_changes:
            await self.publisher.publish_event(
                event_type="road.status_changed",
                entity_id=seg_id,
                payload={
                    "road_segment_id": seg_id,
                    "previous_status": old_st,
                    "new_status": new_st,
                },
            )

        return await self.get_incident_by_id(incident_id)

    async def resolve_incident(
        self,
        incident_id: uuid.UUID,
        resolved_by: uuid.UUID,
        resolution_notes: str,
        verified_clearance: bool = False,
    ) -> Incident:
        """
        Resolves a confirmed incident with mandatory notes.
        Recalculates affected road segments: if no active incidents remain, preserves UNKNOWN unless verified clearance is explicit.
        """
        if not resolution_notes or not resolution_notes.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resolution notes are required when resolving an incident.",
            )

        incident = await self.get_incident_by_id(incident_id)

        # Permitted transition: CONFIRMED -> RESOLVED
        if incident.status != IncidentStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resolve incident in state '{incident.status}'. Only CONFIRMED incidents can be resolved.",
            )

        incident.status = IncidentStatus.RESOLVED.value
        incident.resolved_by = resolved_by
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolution_notes = resolution_notes.strip()

        affected_segment_ids = [
            a.road_segment_id for a in incident.road_associations
            if a.association_type == AssociationType.VERIFIED.value
        ]

        await self.session.flush()

        status_changes = []
        for seg_id in affected_segment_ids:
            change = await self.recalculate_road_segment_state(seg_id, verified_clearance=verified_clearance)
            if change:
                status_changes.append(change)

        record_audit_log(
            session=self.session,
            action="incident_resolved",
            entity_type="incident",
            entity_id=str(incident.id),
            actor_id=resolved_by,
            details={
                "resolution_notes": resolution_notes,
                "verified_clearance": verified_clearance,
                "affected_segments": affected_segment_ids,
            },
        )

        await self.session.commit()

        await self.publisher.publish_event(
            event_type="incident.resolved",
            entity_id=str(incident.id),
            payload={
                "incident_id": str(incident.id),
                "resolved_by": str(resolved_by),
                "notes": resolution_notes,
            },
        )
        for seg_id, old_st, new_st in status_changes:
            await self.publisher.publish_event(
                event_type="road.status_changed",
                entity_id=seg_id,
                payload={
                    "road_segment_id": seg_id,
                    "previous_status": old_st,
                    "new_status": new_st,
                },
            )

        return await self.get_incident_by_id(incident_id)

    async def recalculate_road_segment_state(
        self,
        road_segment_id: str,
        verified_clearance: bool = False,
    ) -> tuple[str, str, str] | None:
        """
        Recalculates the operational state of a road segment taking all active confirmed incidents into account.
        Precedence policy: BLOCKED > RESTRICTED > AT_RISK.
        If no active incidents remain, retains UNKNOWN unless verified clearance is present.
        Returns (road_segment_id, old_status, new_status) if status changed, else None.
        """
        # Find all active, confirmed incidents affecting this segment
        query = (
            select(IncidentRoadAssociation, Incident)
            .join(Incident, IncidentRoadAssociation.incident_id == Incident.id)
            .where(
                IncidentRoadAssociation.road_segment_id == road_segment_id,
                Incident.status == IncidentStatus.CONFIRMED.value,
                IncidentRoadAssociation.association_type == AssociationType.VERIFIED.value,
            )
        )
        res = await self.session.execute(query)
        active_pairs = res.all()

        # Find or create RoadSegmentState
        st_res = await self.session.execute(
            select(RoadSegmentState).where(RoadSegmentState.road_segment_id == road_segment_id)
        )
        road_state = st_res.scalar_one_or_none()
        if not road_state:
            road_state = RoadSegmentState(
                road_segment_id=road_segment_id,
                status=RoadStatus.UNKNOWN.value,
                safety_score=100.0,
            )
            self.session.add(road_state)

        old_status = road_state.status

        if active_pairs:
            impacts = [assoc.assessed_impact.upper() for assoc, _ in active_pairs if assoc.assessed_impact]
            incident_ids = [str(inc.id) for _, inc in active_pairs]

            if AssessedImpact.BLOCKED.value in impacts:
                new_status = RoadStatus.BLOCKED.value
                safety_score = 0.0
                disruption_prob = 1.0
            elif AssessedImpact.RESTRICTED.value in impacts:
                new_status = RoadStatus.RESTRICTED.value
                safety_score = 40.0
                disruption_prob = 0.7
            else:
                new_status = RoadStatus.AT_RISK.value
                safety_score = 60.0
                disruption_prob = 0.4

            road_state.status = new_status
            road_state.safety_score = safety_score
            road_state.disruption_probability = disruption_prob
            road_state.status_reason_codes = [f"incident_{iid}" for iid in incident_ids]
            road_state.source_reference = "active_confirmed_incident"
        else:
            # Critical road-state rule: retain UNKNOWN when no active incidents remain
            # unless verified clearance is explicitly reported
            if verified_clearance:
                new_status = RoadStatus.OPEN.value
                road_state.status = new_status
                road_state.safety_score = 100.0
                road_state.disruption_probability = 0.0
                road_state.status_reason_codes = ["verified_clearance"]
                road_state.source_reference = "official_clearance"
            else:
                new_status = RoadStatus.UNKNOWN.value
                road_state.status = new_status
                road_state.safety_score = 100.0
                road_state.disruption_probability = None
                road_state.status_reason_codes = ["no_active_incidents_retained_unknown"]
                road_state.source_reference = "incident_resolved_retained_unknown"

        road_state.updated_at = datetime.now(timezone.utc)
        self.session.add(road_state)

        if old_status != new_status:
            record_audit_log(
                session=self.session,
                action="road_status_changed",
                entity_type="road_segment",
                entity_id=road_segment_id,
                details={
                    "previous_status": old_status,
                    "new_status": new_status,
                    "active_incidents_count": len(active_pairs),
                },
            )
            return (road_segment_id, old_status, new_status)

        return None
