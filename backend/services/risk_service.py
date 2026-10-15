"""Domain service for Unified Road Risk Scoring, ML Inference, and State Persistence."""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_Centroid, ST_Intersects, ST_MakeEnvelope, ST_X, ST_Y
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.incidents import AssessedImpact, Incident, IncidentRoadAssociation, IncidentStatus
from backend.models.risk import RiskPrediction
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.schemas.risk import RoadRiskItem, RoadRiskListResponse
from backend.services.events import EventPublisher, record_audit_log
from backend.services.weather.weather_service import WeatherService
from ml.inference.unified_risk_pipeline import RouteXUnifiedMLPipeline

logger = logging.getLogger(__name__)
settings = get_settings()

ROAD_CLASS_MAP = {
    "motorway": 0,
    "trunk": 1,
    "primary": 2,
    "secondary": 3,
    "tertiary": 4,
    "unclassified": 3,
    "residential": 4,
    "service": 4,
}


class RiskService:
    """Manages road segment risk predictions, ML feature aggregation, and safe operational state transitions."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()
        self.pipeline: RouteXUnifiedMLPipeline | None = None

    def _get_pipeline(self) -> RouteXUnifiedMLPipeline:
        if self.pipeline is None:
            self.pipeline = RouteXUnifiedMLPipeline()
        return self.pipeline

    def close(self):
        if self.pipeline:
            self.pipeline.close()
            self.pipeline = None

    async def evaluate_segment_risk(
        self,
        road_segment_id: str,
        actor_id: uuid.UUID | None = None,
        force_reeval: bool = False,
    ) -> RiskPrediction:
        """
        Executes unified ML inference (XGBoost landslide + travel delay) for a canonical road segment,
        aggregates real weather observations and terrain features, persists the prediction,
        and safely updates the road segment state adhering to authoritative incident precedence.
        """
        # 1. Fetch road segment with centroid coordinates
        coord_query = select(
            RoadSegment,
            func.ST_Y(func.ST_Centroid(RoadSegment.geom)).label("lat"),
            func.ST_X(func.ST_Centroid(RoadSegment.geom)).label("lon"),
        ).where(RoadSegment.id == road_segment_id)

        res = await self.session.execute(coord_query)
        row = res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Road segment '{road_segment_id}' not found.",
            )

        segment, lat, lon = row
        lat = float(lat)
        lon = float(lon)

        # 2. Gather meteorological feature vector from WeatherService
        now = datetime.now(timezone.utc)
        weather_service = WeatherService(self.session)
        weather_vec = None
        precip_mm = 0.0
        precip_3d_mm = 0.0
        precip_7d_mm = 0.0
        wind_kmh = 12.0
        weather_stale = False
        reason_flags = []

        try:
            weather_vec = await weather_service.get_weather_features_for_ml(
                latitude=lat,
                longitude=lon,
                road_segment_id=road_segment_id,
                reference_time=now,
            )
            if weather_vec:
                precip_mm = float(weather_vec.current_conditions.precipitation_mm or 0.0)
                wind_kmh = float(weather_vec.current_conditions.wind_speed_kmh or 12.0)
                # 24h past accumulation used to compute 3d/7d rolling estimates
                past_24h = float(weather_vec.rainfall_accumulation_past.get("past_24h") or 0.0)
                precip_3d_mm = past_24h * 3.0
                precip_7d_mm = past_24h * 7.0
                weather_stale = bool(weather_vec.is_stale)
                if weather_stale:
                    reason_flags.append("WEATHER_DATA_STALE")
        except Exception as w_err:
            logger.warning(f"Failed to retrieve weather features for segment {road_segment_id}: {w_err}")
            reason_flags.append("WEATHER_DATA_UNAVAILABLE")

        # 3. Execute Unified ML Pipeline (XGBoost landslide + delay regressor)
        road_class_num = ROAD_CLASS_MAP.get(str(segment.road_class).lower(), 3)
        base_speed = float(segment.base_speed_kmh or 45.0)
        current_month = now.month

        pipeline = self._get_pipeline()
        eval_result = pipeline.evaluate_point(
            lat=lat,
            lon=lon,
            road_class=road_class_num,
            base_speed_kmh=base_speed,
            rain_mm=precip_mm,
            precip_3d_mm=precip_3d_mm,
            precip_7d_mm=precip_7d_mm,
            wind_kmh=wind_kmh,
            month=current_month,
        )

        disruption_prob = float(eval_result["disruption_probability"])
        # Safety score: 0-100 where 100 means safer
        safety_score = max(0.0, min(100.0, float(eval_result["safety_score"])))
        confidence = float(eval_result.get("confidence", 0.90))

        # Check terrain validity
        terrain_info = eval_result.get("terrain", {})
        if terrain_info.get("elevation_m") == 0.0 and terrain_info.get("slope_deg") == 0.0:
            reason_flags.append("TERRAIN_FEATURES_APPROXIMATED")
            confidence = max(0.50, confidence - 0.20)

        # Merge model reason codes
        for r in eval_result.get("reasons", []):
            if r not in reason_flags:
                reason_flags.append(r)

        # 4. Check for Authoritative Incidents on this segment
        incident_query = (
            select(IncidentRoadAssociation, Incident)
            .join(Incident, IncidentRoadAssociation.incident_id == Incident.id)
            .where(
                IncidentRoadAssociation.road_segment_id == road_segment_id,
                Incident.status == IncidentStatus.CONFIRMED.value,
            )
        )
        inc_res = await self.session.execute(incident_query)
        active_incidents = inc_res.all()

        is_authoritatively_blocked = False
        is_authoritatively_restricted = False
        authoritative_impacts = []

        for assoc, inc in active_incidents:
            impact = (assoc.assessed_impact or "").upper()
            authoritative_impacts.append(impact)
            if impact == AssessedImpact.BLOCKED.value:
                is_authoritatively_blocked = True
            elif impact == AssessedImpact.RESTRICTED.value:
                is_authoritatively_restricted = True

        # 5. Persist RiskPrediction record
        prediction_id = uuid.uuid4()
        pred = RiskPrediction(
            id=prediction_id,
            road_segment_id=road_segment_id,
            horizon_minutes=settings.ML_RISK_HORIZON_MINUTES,
            disruption_probability=disruption_prob,
            safety_score=safety_score,
            confidence=round(confidence, 2),
            model_name="xgboost_unified_pipeline",
            model_version="1.1.0",
            reason_codes=reason_flags,
            predicted_at=now,
        )
        self.session.add(pred)

        # 6. Update RoadSegmentState with Strict Safety & Precedence Policy
        st_query = select(RoadSegmentState).where(RoadSegmentState.road_segment_id == road_segment_id).with_for_update()
        st_res = await self.session.execute(st_query)
        road_state = st_res.scalar_one_or_none()

        if not road_state:
            road_state = RoadSegmentState(
                road_segment_id=road_segment_id,
                status=RoadStatus.UNKNOWN.value,
                safety_score=100.0,
            )
            self.session.add(road_state)

        old_status = road_state.status

        # Enforce Authoritative Incident Precedence:
        # A model prediction MUST NEVER override or reopen an authoritative confirmed closure!
        if is_authoritatively_blocked:
            new_status = RoadStatus.BLOCKED.value
            controlling_safety = 0.0
            controlling_prob = 1.0
            if "AUTHORITATIVE_CONFIRMED_BLOCKAGE" not in reason_flags:
                reason_flags.insert(0, "AUTHORITATIVE_CONFIRMED_BLOCKAGE")
            score_type = "authoritative_incident"
        elif is_authoritatively_restricted:
            new_status = RoadStatus.RESTRICTED.value
            controlling_safety = min(road_state.safety_score, safety_score)
            controlling_prob = max(road_state.disruption_probability or 0.0, disruption_prob)
            if "AUTHORITATIVE_INCIDENT_RESTRICTION" not in reason_flags:
                reason_flags.insert(0, "AUTHORITATIVE_INCIDENT_RESTRICTION")
            score_type = "authoritative_incident"
        else:
            # Map ML prediction directly to operational state
            if disruption_prob >= 0.80 or safety_score < 30.0:
                new_status = RoadStatus.BLOCKED.value
            elif disruption_prob >= 0.50 or safety_score < 60.0:
                new_status = RoadStatus.AT_RISK.value
            elif disruption_prob >= 0.25 or safety_score < 80.0:
                new_status = RoadStatus.RESTRICTED.value
            else:
                new_status = RoadStatus.OPEN.value

            controlling_safety = safety_score
            controlling_prob = disruption_prob
            score_type = "ml_probabilistic"

        valid_until = now + timedelta(minutes=settings.ML_RISK_HORIZON_MINUTES)
        road_state.status = new_status
        road_state.safety_score = controlling_safety
        road_state.disruption_probability = controlling_prob
        road_state.score_confidence = round(confidence, 2)
        road_state.score_updated_at = now
        road_state.score_valid_until = valid_until
        road_state.score_model_version = "1.1.0"
        road_state.status_reason_codes = reason_flags
        road_state.source_reference = f"ml_risk:{prediction_id}"
        road_state.updated_at = now

        # Record audit log
        record_audit_log(
            session=self.session,
            action="road_risk_scored",
            entity_type="road_segment",
            entity_id=road_segment_id,
            actor_id=actor_id,
            details={
                "prediction_id": str(prediction_id),
                "model_version": "1.1.0",
                "disruption_probability": disruption_prob,
                "safety_score": controlling_safety,
                "confidence": round(confidence, 2),
                "old_status": old_status,
                "new_status": new_status,
                "is_authoritatively_blocked": is_authoritatively_blocked,
                "reason_codes": reason_flags,
            },
        )

        await self.session.commit()
        await self.session.refresh(pred)

        # Publish event for real-time subscribers & frontend map
        await self.publisher.publish_event(
            event_type="road.risk_updated",
            entity_id=road_segment_id,
            payload={
                "road_segment_id": road_segment_id,
                "status": new_status,
                "safety_score": controlling_safety,
                "disruption_probability": controlling_prob,
                "score_confidence": round(confidence, 2),
                "score_type": score_type,
                "model_version": "1.1.0",
                "reason_codes": reason_flags,
                "valid_until": valid_until.isoformat(),
            },
        )

        return pred

    async def get_road_risk(
        self,
        min_lat: float | None = None,
        min_lon: float | None = None,
        max_lat: float | None = None,
        max_lon: float | None = None,
        road_segment_ids: list[str] | None = None,
        status_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> RoadRiskListResponse:
        """
        Retrieves segment-level risk predictions and operational states.
        Correctly distinguishes verified low risk from UNKNOWN, stale, or incomplete data.
        """
        query = (
            select(
                RoadSegment,
                RoadSegmentState,
                func.ST_AsGeoJSON(RoadSegment.geom).label("geojson_geom"),
            )
            .outerjoin(RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id)
        )
        count_query = select(func.count(RoadSegment.id))

        # Spatial bounding box filter
        if min_lat is not None and min_lon is not None and max_lat is not None and max_lon is not None:
            if min_lat >= max_lat or min_lon >= max_lon:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid bounding box: min coordinates must be strictly less than max coordinates.",
                )
            bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = query.where(ST_Intersects(RoadSegment.geom, bbox_geom))
            count_query = count_query.where(ST_Intersects(RoadSegment.geom, bbox_geom))

        # Explicit road segment ID filter
        if road_segment_ids:
            query = query.where(RoadSegment.id.in_(road_segment_ids))
            count_query = count_query.where(RoadSegment.id.in_(road_segment_ids))

        # Status filter
        if status_filter:
            query = query.where(RoadSegmentState.status == status_filter.upper())
            count_query = count_query.outerjoin(
                RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id
            ).where(RoadSegmentState.status == status_filter.upper())

        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(RoadSegment.id).limit(limit).offset(offset)
        res = await self.session.execute(query)

        now = datetime.now(timezone.utc)
        items: list[RoadRiskItem] = []

        for seg, st, geojson_raw in res.all():
            coords = []
            if geojson_raw:
                try:
                    gdict = json.loads(geojson_raw)
                    coords = gdict.get("coordinates", [])
                except Exception:
                    pass

            if st:
                curr_status = st.status
                safety = st.safety_score
                disruption_prob = st.disruption_probability
                conf = st.score_confidence
                m_ver = st.score_model_version
                reasons = list(st.status_reason_codes or [])
                updated_at = st.score_updated_at or st.updated_at
                valid_until = st.score_valid_until
                is_unknown = (curr_status == RoadStatus.UNKNOWN.value) or (st.score_updated_at is None)

                # Freshness calculation
                is_stale = False
                if is_unknown or st.score_updated_at is None:
                    is_stale = True
                elif valid_until and valid_until < now:
                    is_stale = True
                elif updated_at and (now - updated_at) > timedelta(minutes=settings.ML_RISK_STALE_MINUTES):
                    is_stale = True

                score_type = "authoritative_incident" if curr_status == "BLOCKED" and "AUTHORITATIVE_CONFIRMED_BLOCKAGE" in reasons else ("ml_probabilistic" if not is_unknown else "unknown")
            else:
                curr_status = RoadStatus.UNKNOWN.value
                safety = 100.0  # default schema fallback
                disruption_prob = None
                conf = None
                m_ver = None
                reasons = ["NO_ASSESSMENT_RECORDED"]
                updated_at = None
                valid_until = None
                is_stale = True
                is_unknown = True
                score_type = "unknown"

            items.append(
                RoadRiskItem(
                    road_segment_id=seg.id,
                    road_name=seg.name,
                    road_class=seg.road_class,
                    length_m=seg.length_m,
                    status=curr_status,
                    safety_score=safety,
                    disruption_probability=disruption_prob,
                    score_confidence=conf,
                    score_type=score_type,
                    model_name="xgboost_unified_pipeline" if not is_unknown else None,
                    model_version=m_ver,
                    reason_codes=reasons,
                    is_stale=is_stale,
                    is_unknown=is_unknown,
                    score_updated_at=updated_at,
                    score_valid_until=valid_until,
                    coordinates=coords,
                )
            )

        return RoadRiskListResponse(total=total, limit=limit, offset=offset, items=items)

    async def get_segment_risk_detail(self, road_segment_id: str) -> RoadRiskItem:
        """Retrieves real-time risk assessment and score semantics for a single segment."""
        resp = await self.get_road_risk(road_segment_ids=[road_segment_id], limit=1)
        if not resp.items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Road segment '{road_segment_id}' not found.",
            )
        return resp.items[0]
