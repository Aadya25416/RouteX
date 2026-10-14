"""Domain service calculating road-segment traffic metrics from GPS telemetry."""

import logging
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.logistics import VehicleLocation
from backend.models.observations import TrafficObservation
from backend.models.roads import RoadSegment
from backend.schemas.traffic import TrafficAggregationSummary, TrafficObservationResponse
from backend.services.events import EventPublisher, record_audit_log

logger = logging.getLogger(__name__)
settings = get_settings()


class TrafficService:
    """Aggregates vehicle GPS telemetry into segment-level speed, congestion, and confidence metrics."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()

    async def calculate_traffic_conditions(
        self,
        window_minutes: int = 30,
        min_samples_for_high_confidence: int = 5,
        actor_id: uuid.UUID | None = None,
    ) -> TrafficAggregationSummary:
        """
        Analyzes vehicle GPS tracks within the given time window and calculates
        average/median speeds, congestion ratios, and honest data-sufficiency indicators.
        """
        now = datetime.now(timezone.utc)
        window_end = now
        window_start = window_end - timedelta(minutes=window_minutes)

        # 1. Fetch GPS fixes recorded within this window having matched segment
        query = (
            select(
                VehicleLocation.matched_segment_id,
                VehicleLocation.speed_kmh,
                VehicleLocation.recorded_at,
            )
            .where(
                VehicleLocation.matched_segment_id.isnot(None),
                VehicleLocation.recorded_at >= window_start,
                VehicleLocation.recorded_at <= window_end,
            )
        )
        res = await self.session.execute(query)
        rows = res.all()

        # Group by road_segment_id
        segment_samples: dict[str, list[dict[str, Any]]] = {}
        for seg_id, speed, rec_time in rows:
            if seg_id not in segment_samples:
                segment_samples[seg_id] = []
            segment_samples[seg_id].append({"speed": speed, "time": rec_time})

        # Fetch base speeds for segments to compute congestion ratios
        active_seg_ids = list(segment_samples.keys())
        base_speeds: dict[str, float] = {}
        if active_seg_ids:
            seg_res = await self.session.execute(
                select(RoadSegment.id, RoadSegment.base_speed_kmh).where(RoadSegment.id.in_(active_seg_ids))
            )
            for sid, bspeed in seg_res.all():
                base_speeds[sid] = bspeed or 40.0

        persisted_records = 0
        high_conf_count = 0
        insufficient_count = 0
        total_samples = len(rows)

        for seg_id, samples in segment_samples.items():
            sample_count = len(samples)
            speeds = [s["speed"] for s in samples if s["speed"] is not None]
            newest_sample_time = max(s["time"] for s in samples)
            freshness_seconds = max(0.0, (window_end - newest_sample_time).total_seconds())

            avg_speed = statistics.mean(speeds) if speeds else None
            median_speed = statistics.median(speeds) if speeds else None

            base_speed = base_speeds.get(seg_id, 40.0)
            congestion_ratio = None
            if avg_speed is not None and base_speed > 0:
                congestion_ratio = round(avg_speed / base_speed, 3)

            # Confidence determination: strictly honor sample sufficiency
            if sample_count >= min_samples_for_high_confidence:
                confidence = "HIGH"
                high_conf_count += 1
            elif sample_count >= 3:
                confidence = "MEDIUM"
            elif sample_count >= 1:
                confidence = "LOW"
            else:
                confidence = "INSUFFICIENT_DATA"
                insufficient_count += 1

            # Check if an observation for this segment and window_end already recorded
            existing = await self.session.execute(
                select(TrafficObservation.id).where(
                    TrafficObservation.road_segment_id == seg_id,
                    TrafficObservation.window_end == window_end,
                )
            )
            if existing.scalar_one_or_none():
                continue

            obs = TrafficObservation(
                id=uuid.uuid4(),
                road_segment_id=seg_id,
                window_start=window_start,
                window_end=window_end,
                sample_count=sample_count,
                avg_speed_kmh=round(avg_speed, 2) if avg_speed is not None else None,
                median_speed_kmh=round(median_speed, 2) if median_speed is not None else None,
                congestion_ratio=congestion_ratio,
                confidence=confidence,
                data_freshness_seconds=round(freshness_seconds, 1),
                created_at=now,
            )
            self.session.add(obs)
            persisted_records += 1

        record_audit_log(
            session=self.session,
            action="traffic_conditions_calculated",
            entity_type="traffic_aggregation",
            entity_id=f"window_{int(window_end.timestamp())}",
            actor_id=actor_id,
            details={
                "segments_calculated": persisted_records,
                "total_samples": total_samples,
                "window_minutes": window_minutes,
            },
        )
        await self.session.commit()

        # Publish event
        await self.publisher.publish_event(
            event_type="traffic.updated",
            entity_id=f"window_{int(window_end.timestamp())}",
            payload={
                "segments_aggregated": persisted_records,
                "total_samples": total_samples,
                "window_end": window_end.isoformat(),
            },
        )

        return TrafficAggregationSummary(
            segments_aggregated=persisted_records,
            window_start=window_start,
            window_end=window_end,
            total_samples_analyzed=total_samples,
            high_confidence_segments=high_conf_count,
            insufficient_data_segments=insufficient_count,
        )

    async def get_traffic_observations(
        self,
        road_segment_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TrafficObservationResponse]:
        """Retrieves recent traffic metrics for road segments."""
        query = select(TrafficObservation)
        if road_segment_id:
            query = query.where(TrafficObservation.road_segment_id == road_segment_id)

        res = await self.session.execute(
            query.order_by(TrafficObservation.window_end.desc()).limit(limit).offset(offset)
        )
        return [TrafficObservationResponse.model_validate(obs) for obs in res.scalars().all()]
