"""Road network read and GeoJSON API endpoints."""

import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_Intersects, ST_MakeEnvelope
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import get_async_session
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.schemas.roads import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONFeatureProperties,
    GeoJSONGeometry,
    RoadListResponse,
    RoadSegmentDetail,
    RoadSegmentListItem,
)

router = APIRouter(prefix="/roads", tags=["Roads"])
settings = get_settings()


@router.get("", response_model=RoadListResponse)
async def list_roads(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    min_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="South latitude")] = None,
    min_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="West longitude")] = None,
    max_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="North latitude")] = None,
    max_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="East longitude")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    road_class: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum number of items")] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RoadListResponse:
    """Lists bounded road segments with optional bounding box and status filtering."""
    query = (
        select(RoadSegment, RoadSegmentState)
        .outerjoin(RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id)
    )

    count_query = select(func.count(RoadSegment.id))

    # Apply bounding box filter if all 4 corners are provided
    if min_lat is not None and min_lon is not None and max_lat is not None and max_lon is not None:
        if min_lat >= max_lat or min_lon >= max_lon:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bounding box: min coordinates must be strictly less than max coordinates",
            )
        bbox_geom = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = query.where(ST_Intersects(RoadSegment.geom, bbox_geom))
        count_query = count_query.where(ST_Intersects(RoadSegment.geom, bbox_geom))

    if status_filter:
        query = query.where(RoadSegmentState.status == status_filter.upper())
        count_query = count_query.outerjoin(
            RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id
        ).where(RoadSegmentState.status == status_filter.upper())

    if road_class:
        query = query.where(RoadSegment.road_class == road_class)
        count_query = count_query.where(RoadSegment.road_class == road_class)

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(RoadSegment.id).limit(limit).offset(offset)
    results = await session.execute(query)

    items: list[RoadSegmentListItem] = []
    for seg, st in results.all():
        current_status = st.status if st else RoadStatus.UNKNOWN.value
        current_score = st.safety_score if st else 100.0
        items.append(
            RoadSegmentListItem(
                id=seg.id,
                osm_way_id=seg.osm_way_id,
                u_node_id=seg.u_node_id,
                v_node_id=seg.v_node_id,
                name=seg.name,
                road_class=seg.road_class,
                length_m=seg.length_m,
                base_speed_kmh=seg.base_speed_kmh,
                base_travel_time_s=seg.base_travel_time_s,
                oneway=seg.oneway,
                status=current_status,
                safety_score=current_score,
            )
        )

    return RoadListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/geojson", response_model=GeoJSONFeatureCollection)
async def get_roads_geojson(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    min_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="South latitude")] = None,
    min_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="West longitude")] = None,
    max_lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="North latitude")] = None,
    max_lon: Annotated[float | None, Query(ge=-180.0, le=180.0, description="East longitude")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Max GeoJSON features to return")] = 200,
) -> GeoJSONFeatureCollection:
    """Returns bounded road segments formatted as a GeoJSON FeatureCollection."""
    # Fallback to configured corridor bounds if bounding box is not provided
    s_lat = min_lat if min_lat is not None else settings.CORRIDOR_MIN_LAT
    w_lon = min_lon if min_lon is not None else settings.CORRIDOR_MIN_LON
    n_lat = max_lat if max_lat is not None else settings.CORRIDOR_MAX_LAT
    e_lon = max_lon if max_lon is not None else settings.CORRIDOR_MAX_LON

    if s_lat >= n_lat or w_lon >= e_lon:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bounding box: south/west must be strictly less than north/east",
        )

    bbox_geom = ST_MakeEnvelope(w_lon, s_lat, e_lon, n_lat, 4326)

    query = (
        select(
            RoadSegment,
            RoadSegmentState,
            func.ST_AsGeoJSON(RoadSegment.geom).label("geojson_geom"),
        )
        .outerjoin(RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id)
        .where(ST_Intersects(RoadSegment.geom, bbox_geom))
    )

    if status_filter:
        query = query.where(RoadSegmentState.status == status_filter.upper())

    query = query.order_by(RoadSegment.id).limit(limit)
    results = await session.execute(query)

    features: list[GeoJSONFeature] = []
    for seg, st, geojson_raw in results.all():
        geom_dict = json.loads(geojson_raw)
        current_status = st.status if st else RoadStatus.UNKNOWN.value
        current_score = st.safety_score if st else 100.0
        disruption_prob = st.disruption_probability if st else None

        features.append(
            GeoJSONFeature(
                id=seg.id,
                geometry=GeoJSONGeometry(
                    type="LineString",
                    coordinates=geom_dict.get("coordinates", []),
                ),
                properties=GeoJSONFeatureProperties(
                    id=seg.id,
                    name=seg.name,
                    road_class=seg.road_class,
                    length_m=seg.length_m,
                    oneway=seg.oneway,
                    status=current_status,
                    safety_score=current_score,
                    disruption_probability=disruption_prob,
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


@router.get("/{road_id}", response_model=RoadSegmentDetail)
async def get_road_detail(
    road_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RoadSegmentDetail:
    """Retrieves complete details and geometry for a single canonical road segment."""
    query = (
        select(
            RoadSegment,
            RoadSegmentState,
            func.ST_AsGeoJSON(RoadSegment.geom).label("geojson_geom"),
        )
        .outerjoin(RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id)
        .where(RoadSegment.id == road_id)
    )

    result = await session.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Road segment with id '{road_id}' not found",
        )

    seg, st, geojson_raw = row
    geom_dict = json.loads(geojson_raw)

    current_status = st.status if st else RoadStatus.UNKNOWN.value
    current_score = st.safety_score if st else 100.0
    disruption_prob = st.disruption_probability if st else None
    score_conf = st.score_confidence if st else None
    valid_until = st.score_valid_until if st else None
    reason_codes = st.status_reason_codes if st else []
    source_ref = st.source_reference if st else None

    return RoadSegmentDetail(
        id=seg.id,
        osm_way_id=seg.osm_way_id,
        u_node_id=seg.u_node_id,
        v_node_id=seg.v_node_id,
        key=seg.key,
        name=seg.name,
        road_class=seg.road_class,
        length_m=seg.length_m,
        base_speed_kmh=seg.base_speed_kmh,
        base_travel_time_s=seg.base_travel_time_s,
        oneway=seg.oneway,
        access_allowed=seg.access_allowed,
        bridge=seg.bridge,
        tunnel=seg.tunnel,
        corridor_name=seg.corridor_name,
        status=current_status,
        safety_score=current_score,
        disruption_probability=disruption_prob,
        score_confidence=score_conf,
        score_valid_until=valid_until,
        status_reason_codes=reason_codes,
        source_reference=source_ref,
        coordinates=geom_dict.get("coordinates", []),
    )
