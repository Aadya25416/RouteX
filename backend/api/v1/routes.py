"""Route planning and recommendation endpoints."""

import json
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user
from backend.database import get_async_session
from backend.models.routing import RouteMode, RouteRecommendation
from backend.models.users import User
from backend.schemas.routing import (
    RoutePlanRequest,
    RouteRecommendationResponse,
    SafetySummary,
    SnappedPoint,
)
from backend.services.routing_engine import RoutingEngine

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("/plan", response_model=RouteRecommendationResponse)
async def plan_route(
    payload: RoutePlanRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RouteRecommendationResponse:
    """
    Computes an optimal path on the directed road network using SHORTEST_DISTANCE or FASTEST_SAFE mode.
    Enforces road disruption constraints and safety policies.
    """
    engine = RoutingEngine(session)
    return await engine.calculate_route(
        origin_lat=payload.origin_lat,
        origin_lon=payload.origin_lon,
        destination_lat=payload.destination_lat,
        destination_lon=payload.destination_lon,
        mode=payload.mode,
        trip_id=payload.trip_id,
        max_snapping_distance_m=payload.max_snapping_distance_m,
        require_verified_safe=payload.require_verified_safe,
        persist=True,
    )


@router.get("/{route_id}", response_model=RouteRecommendationResponse)
async def get_route(
    route_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RouteRecommendationResponse:
    """Retrieves a persisted route recommendation by ID."""
    query = select(
        RouteRecommendation,
        func.ST_AsGeoJSON(RouteRecommendation.route_geom).label("geojson"),
    ).where(RouteRecommendation.id == route_id)

    res = await session.execute(query)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route recommendation '{route_id}' not found.",
        )

    rec, geojson_str = row
    geojson_data = json.loads(geojson_str) if geojson_str else {"type": "LineString", "coordinates": []}

    safety_dict = rec.safety_summary or {}
    safety_summary = SafetySummary(
        safety_status=safety_dict.get("safety_status", "UNVERIFIED"),
        meets_safety_policy=rec.meets_safety_policy,
        unknown_segment_count=safety_dict.get("unknown_segment_count", 0),
        at_risk_segment_count=safety_dict.get("at_risk_segment_count", 0),
        restricted_segment_count=safety_dict.get("restricted_segment_count", 0),
        blocked_segment_count=safety_dict.get("blocked_segment_count", 0),
        unknown_segments=safety_dict.get("unknown_segments", []),
        at_risk_segments=safety_dict.get("at_risk_segments", []),
        restricted_segments=safety_dict.get("restricted_segments", []),
        disclaimer=safety_dict.get("disclaimer"),
        reasons=safety_dict.get("reasons", []),
    )

    snapped_orig = SnappedPoint(
        node_id=rec.snapped_origin_node_id or "",
        distance_m=rec.snapped_origin_distance_m or 0.0,
        latitude=0.0,
        longitude=0.0,
    )
    snapped_dest = SnappedPoint(
        node_id=rec.snapped_destination_node_id or "",
        distance_m=rec.snapped_destination_distance_m or 0.0,
        latitude=0.0,
        longitude=0.0,
    )

    return RouteRecommendationResponse(
        id=rec.id,
        trip_id=rec.trip_id,
        mode=RouteMode(rec.mode) if rec.mode in RouteMode.__members__ else RouteMode.SHORTEST_DISTANCE,
        snapped_origin=snapped_orig,
        snapped_destination=snapped_dest,
        ordered_node_ids=rec.ordered_node_ids or [],
        ordered_segment_ids=rec.ordered_segment_ids or [],
        route_geojson=geojson_data,
        distance_m=rec.distance_m,
        eta_seconds=rec.eta_seconds,
        meets_safety_policy=rec.meets_safety_policy,
        safety_summary=safety_summary,
        avoided_hazard_count=rec.avoided_hazard_count,
        reason=rec.reason,
        computed_at=rec.computed_at,
    )
