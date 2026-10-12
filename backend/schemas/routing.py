"""Pydantic schemas for Routing Engine and Route Recommendations."""

import uuid
from datetime import datetime
from typing import Annotated, Any
from pydantic import BaseModel, Field

from backend.models.routing import RouteMode


class RoutePlanRequest(BaseModel):
    """Request to compute an optimal route between two coordinates."""
    origin_lat: Annotated[float, Field(ge=-90.0, le=90.0, description="Origin latitude")]
    origin_lon: Annotated[float, Field(ge=-180.0, le=180.0, description="Origin longitude")]
    destination_lat: Annotated[float, Field(ge=-90.0, le=90.0, description="Destination latitude")]
    destination_lon: Annotated[float, Field(ge=-180.0, le=180.0, description="Destination longitude")]
    mode: RouteMode = RouteMode.SHORTEST_DISTANCE
    trip_id: uuid.UUID | None = None
    max_snapping_distance_m: Annotated[float, Field(ge=50.0, le=50000.0, default=10000.0)] = 10000.0
    require_verified_safe: bool = Field(
        default=False,
        description="If True, rejects routes with UNKNOWN road states and requires verified safety.",
    )


class SnappedPoint(BaseModel):
    node_id: str
    distance_m: float
    latitude: float
    longitude: float


class SafetySummary(BaseModel):
    safety_status: str = Field(description="VERIFIED_SAFE, UNVERIFIED, AT_RISK, or RESTRICTED")
    meets_safety_policy: bool
    unknown_segment_count: int = 0
    at_risk_segment_count: int = 0
    restricted_segment_count: int = 0
    blocked_segment_count: int = 0
    unknown_segments: list[str] = Field(default_factory=list)
    at_risk_segments: list[str] = Field(default_factory=list)
    restricted_segments: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    reasons: list[str] = Field(default_factory=list)


class RouteRecommendationResponse(BaseModel):
    id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None
    mode: RouteMode
    snapped_origin: SnappedPoint
    snapped_destination: SnappedPoint
    ordered_node_ids: list[str]
    ordered_segment_ids: list[str]
    route_geojson: dict[str, Any]
    distance_m: float
    eta_seconds: float
    meets_safety_policy: bool
    safety_summary: SafetySummary
    avoided_hazard_count: int = 0
    reason: str | None = None
    computed_at: datetime


class RerouteResponse(BaseModel):
    trip_id: uuid.UUID
    status: str = Field(description="REROUTED, NO_SAFE_ROUTE, or UNAFFECTED")
    disruption_segment_ids: list[str] = Field(default_factory=list)
    previous_route_id: uuid.UUID | None = None
    new_route: RouteRecommendationResponse | None = None
    message: str
