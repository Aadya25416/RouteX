"""Road network schemas for REST and GeoJSON representations."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class RoadSegmentListItem(BaseModel):
    id: str
    osm_way_id: int | None = None
    u_node_id: str
    v_node_id: str
    name: str | None = None
    road_class: str
    length_m: float
    base_speed_kmh: float | None = None
    base_travel_time_s: float
    oneway: bool
    status: str = "UNKNOWN"
    safety_score: float = 100.0


class RoadSegmentDetail(BaseModel):
    id: str
    osm_way_id: int | None = None
    u_node_id: str
    v_node_id: str
    key: int = 0
    name: str | None = None
    road_class: str
    length_m: float
    base_speed_kmh: float | None = None
    base_travel_time_s: float
    oneway: bool
    access_allowed: bool
    bridge: bool
    tunnel: bool
    corridor_name: str | None = None
    status: str = "UNKNOWN"
    safety_score: float = 100.0
    disruption_probability: float | None = None
    score_confidence: float | None = None
    score_valid_until: datetime | None = None
    status_reason_codes: list[str] = Field(default_factory=list)
    source_reference: str | None = None
    coordinates: list[list[float]] = Field(description="LineString coordinates [lon, lat]")


class RoadListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RoadSegmentListItem]


class GeoJSONGeometry(BaseModel):
    type: str = "LineString"
    coordinates: list[list[float]]


class GeoJSONFeatureProperties(BaseModel):
    id: str
    name: str | None = None
    road_class: str
    length_m: float
    oneway: bool
    status: str = "UNKNOWN"
    safety_score: float = 100.0
    disruption_probability: float | None = None


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: str
    geometry: GeoJSONGeometry
    properties: GeoJSONFeatureProperties


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]
