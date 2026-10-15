"""Dashboard Service for aggregating operational telemetry and system metrics."""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.audit import Alert, AuditLog
from backend.models.base import utc_now
from backend.models.incidents import Incident
from backend.models.logistics import (
    Delivery,
    DeliveryPriority,
    DeliveryStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
)
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.models.users import User
from backend.schemas.dashboard import (
    AlertSummary,
    DashboardMetricsResponse,
    DeliverySummary,
    IncidentSeveritySummary,
    IncidentStatusSummary,
    RoadStatusSummary,
    TripSummary,
    VehicleFleetSummary,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class DashboardService:
    """Computes real-time, database-backed operational metrics for corridor dashboards."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_metrics(self, current_user: User) -> DashboardMetricsResponse:
        """
        Calculates corridor operational metrics strictly from database records.
        Applies role-based filtering where appropriate.
        """
        now = utc_now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        fifteen_minutes_ago = now - timedelta(minutes=15)

        # 1. Incident Aggregates
        inc_status_res = await self.session.execute(
            select(Incident.status, func.count(Incident.id)).group_by(Incident.status)
        )
        inc_status_counts = {row[0].upper(): row[1] for row in inc_status_res.all() if row[0]}

        inc_sev_res = await self.session.execute(
            select(Incident.severity, func.count(Incident.id)).group_by(Incident.severity)
        )
        inc_sev_counts = {row[0].upper(): row[1] for row in inc_sev_res.all() if row[0]}

        submitted = inc_status_counts.get("SUBMITTED", 0)
        under_review = inc_status_counts.get("UNDER_REVIEW", 0)
        confirmed = inc_status_counts.get("CONFIRMED", 0)
        resolved = inc_status_counts.get("RESOLVED", 0)
        rejected = inc_status_counts.get("REJECTED", 0)
        total_incidents = sum(inc_status_counts.values())

        incident_summary = IncidentStatusSummary(
            submitted=submitted,
            under_review=under_review,
            confirmed=confirmed,
            resolved=resolved,
            rejected=rejected,
            total=total_incidents,
            active_unresolved=submitted + under_review + confirmed,
        )

        incident_severities = IncidentSeveritySummary(
            critical=inc_sev_counts.get("CRITICAL", 0),
            high=inc_sev_counts.get("HIGH", 0),
            medium=inc_sev_counts.get("MEDIUM", 0),
            low=inc_sev_counts.get("LOW", 0),
        )

        # 2. Road Network Aggregates
        total_roads_res = await self.session.execute(select(func.count(RoadSegment.id)))
        total_roads = total_roads_res.scalar_one() or 0

        road_res = await self.session.execute(
            select(RoadSegmentState.status, func.count(RoadSegmentState.id)).group_by(RoadSegmentState.status)
        )
        road_counts = {row[0].upper(): row[1] for row in road_res.all() if row[0]}

        open_roads = road_counts.get(RoadStatus.OPEN.value, 0)
        at_risk_roads = road_counts.get(RoadStatus.AT_RISK.value, 0)
        restricted_roads = road_counts.get(RoadStatus.RESTRICTED.value, 0)
        blocked_roads = road_counts.get(RoadStatus.BLOCKED.value, 0)
        unknown_roads = road_counts.get(RoadStatus.UNKNOWN.value, 0)

        road_summary = RoadStatusSummary(
            open=open_roads,
            at_risk=at_risk_roads,
            restricted=restricted_roads,
            blocked=blocked_roads,
            unknown=unknown_roads,
            total=total_roads if total_roads > 0 else sum(road_counts.values()),
        )

        # 3. Vehicle Fleet Aggregates
        veh_res = await self.session.execute(
            select(Vehicle.status, func.count(Vehicle.id)).group_by(Vehicle.status)
        )
        veh_counts = {row[0].upper(): row[1] for row in veh_res.all() if row[0]}

        total_veh_res = await self.session.execute(select(func.count(Vehicle.id)))
        total_vehicles = total_veh_res.scalar_one() or 0

        # Check live tracking active (distinct vehicles with GPS fixes in the last 15 minutes)
        live_gps_res = await self.session.execute(
            select(func.count(func.distinct(VehicleLocation.vehicle_id))).where(
                VehicleLocation.recorded_at >= fifteen_minutes_ago
            )
        )
        live_tracking_count = live_gps_res.scalar_one() or 0

        vehicle_summary = VehicleFleetSummary(
            total=total_vehicles,
            available=veh_counts.get(VehicleStatus.AVAILABLE.value, 0),
            in_transit=veh_counts.get(VehicleStatus.IN_TRANSIT.value, 0),
            maintenance=veh_counts.get(VehicleStatus.MAINTENANCE.value, 0),
            inactive=veh_counts.get(VehicleStatus.DECOMMISSIONED.value, 0),
            live_tracking_active=live_tracking_count,
        )

        # 4. Trip Aggregates
        trip_res = await self.session.execute(
            select(Trip.status, func.count(Trip.id)).group_by(Trip.status)
        )
        trip_counts = {row[0].upper(): row[1] for row in trip_res.all() if row[0]}

        planned_trips = trip_counts.get(TripStatus.PLANNED.value, 0)
        in_transit_trips = trip_counts.get(TripStatus.IN_TRANSIT.value, 0)
        paused_trips = trip_counts.get(TripStatus.PAUSED.value, 0)
        completed_trips = trip_counts.get(TripStatus.COMPLETED.value, 0)
        cancelled_trips = trip_counts.get(TripStatus.CANCELLED.value, 0)
        total_trips = sum(trip_counts.values())

        # Recent reroutes in past 24 hours from AuditLog
        reroute_audit_res = await self.session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "trip_rerouted",
                AuditLog.created_at >= twenty_four_hours_ago,
            )
        )
        recent_reroutes = reroute_audit_res.scalar_one() or 0

        trip_summary = TripSummary(
            total=total_trips,
            planned=planned_trips,
            in_transit=in_transit_trips,
            paused=paused_trips,
            completed=completed_trips,
            cancelled=cancelled_trips,
            active_count=planned_trips + in_transit_trips + paused_trips,
            recent_reroutes=recent_reroutes,
        )

        # 5. Delivery Aggregates
        deliv_res = await self.session.execute(
            select(Delivery.status, func.count(Delivery.id)).group_by(Delivery.status)
        )
        deliv_counts = {row[0].upper(): row[1] for row in deliv_res.all() if row[0]}

        priority_deliv_res = await self.session.execute(
            select(func.count(Delivery.id)).where(
                Delivery.priority.in_([DeliveryPriority.HIGH.value, DeliveryPriority.CRITICAL.value]),
                Delivery.status != DeliveryStatus.DELIVERED.value,
            )
        )
        priority_count = priority_deliv_res.scalar_one() or 0
        total_deliveries = sum(deliv_counts.values())

        delivery_summary = DeliverySummary(
            total=total_deliveries,
            pending=deliv_counts.get(DeliveryStatus.PENDING.value, 0),
            dispatched=deliv_counts.get(DeliveryStatus.ASSIGNED.value, 0),
            in_transit=deliv_counts.get(DeliveryStatus.IN_TRANSIT.value, 0),
            delivered=deliv_counts.get(DeliveryStatus.DELIVERED.value, 0),
            priority_count=priority_count,
        )

        # 6. Alert Aggregates (scoped to user's authorized visibility)
        if current_user.role == "driver":
            user_filter = (Alert.recipient_user_id == current_user.id)
        else:
            user_filter = (
                (Alert.recipient_user_id == current_user.id)
                | (Alert.recipient_role.in_(["dispatcher", "admin"]))
                | (Alert.recipient_role.is_(None))
            )

        unack_alerts_res = await self.session.execute(
            select(func.count(Alert.id)).where(
                user_filter,
                Alert.is_acknowledged == False,  # noqa: E712
            )
        )
        unack_alerts_count = unack_alerts_res.scalar_one() or 0

        crit_unack_res = await self.session.execute(
            select(func.count(Alert.id)).where(
                user_filter,
                Alert.is_acknowledged == False,  # noqa: E712
                Alert.severity == "critical",
            )
        )
        crit_unack_count = crit_unack_res.scalar_one() or 0

        recent_alerts_res = await self.session.execute(
            select(func.count(Alert.id)).where(
                user_filter,
                Alert.created_at >= twenty_four_hours_ago,
            )
        )
        recent_alerts_count = recent_alerts_res.scalar_one() or 0

        alert_summary = AlertSummary(
            total_unacknowledged=unack_alerts_count,
            critical_unacknowledged=crit_unack_count,
            recent_count=recent_alerts_count,
        )

        return DashboardMetricsResponse(
            corridor_name=settings.CORRIDOR_NAME,
            generated_at=now,
            incidents=incident_summary,
            incident_severities=incident_severities,
            roads=road_summary,
            vehicles=vehicle_summary,
            trips=trip_summary,
            deliveries=delivery_summary,
            alerts=alert_summary,
        )
