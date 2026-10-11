"""Tests for road network REST and GeoJSON read APIs."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus


@pytest_asyncio.fixture(autouse=True)
async def setup_test_roads(db_session: AsyncSession):
    """Seed sample road segment for API testing and clean up afterward."""
    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'api_node_%';"))
    await db_session.commit()

    n1 = RoadNode(
        id="api_node_1",
        osm_node_id=2001,
        geom="SRID=4326;POINT(91.7360 26.1440)",
        longitude=91.7360,
        latitude=26.1440,
    )
    n2 = RoadNode(
        id="api_node_2",
        osm_node_id=2002,
        geom="SRID=4326;POINT(91.7380 26.1460)",
        longitude=91.7380,
        latitude=26.1460,
    )
    db_session.add_all([n1, n2])
    await db_session.flush()

    edge = RoadSegment(
        id="api_edge_1",
        osm_way_id=9001,
        u_node_id="api_node_1",
        v_node_id="api_node_2",
        key=0,
        geom="SRID=4326;LINESTRING(91.7360 26.1440, 91.7380 26.1460)",
        length_m=350.0,
        base_speed_kmh=40.0,
        base_travel_time_s=31.5,
        road_class="primary",
        name="Assam Trunk Road",
        oneway=False,
        access_allowed=True,
        corridor_name="Guwahati-Tawang",
    )
    db_session.add(edge)
    await db_session.flush()

    state = RoadSegmentState(
        road_segment_id="api_edge_1",
        status=RoadStatus.UNKNOWN.value,
        safety_score=95.0,
        disruption_probability=0.05,
        status_reason_codes=["sample_test"],
    )
    db_session.add(state)
    await db_session.commit()

    yield

    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'api_node_%';"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_roads_pagination(async_client: AsyncClient):
    response = await async_client.get("/api/v1/roads?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["items"]) >= 1

    item = next(it for it in data["items"] if it["id"] == "api_edge_1")
    assert item["name"] == "Assam Trunk Road"
    assert item["road_class"] == "primary"
    assert item["status"] == "UNKNOWN"
    assert item["safety_score"] == 95.0


@pytest.mark.asyncio
async def test_list_roads_bbox_filter(async_client: AsyncClient):
    # Query within bounds containing api_edge_1 (Guwahati area)
    response = await async_client.get(
        "/api/v1/roads?min_lat=26.10&min_lon=91.70&max_lat=26.20&max_lon=91.80"
    )
    assert response.status_code == 200
    data = response.json()
    assert any(it["id"] == "api_edge_1" for it in data["items"])

    # Query far outside (e.g. southern India) returns empty
    response_outside = await async_client.get(
        "/api/v1/roads?min_lat=12.0&min_lon=77.0&max_lat=13.0&max_lon=78.0"
    )
    assert response_outside.status_code == 200
    data_outside = response_outside.json()
    assert not any(it["id"] == "api_edge_1" for it in data_outside["items"])


@pytest.mark.asyncio
async def test_list_roads_invalid_bbox_error(async_client: AsyncClient):
    # Inverted min/max coordinates must return 400 Bad Request
    response = await async_client.get(
        "/api/v1/roads?min_lat=27.0&min_lon=91.70&max_lat=26.0&max_lon=91.80"
    )
    assert response.status_code == 400
    assert "min coordinates must be strictly less than max" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_road_detail_success(async_client: AsyncClient):
    response = await async_client.get("/api/v1/roads/api_edge_1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "api_edge_1"
    assert data["name"] == "Assam Trunk Road"
    assert data["length_m"] == 350.0
    assert data["status"] == "UNKNOWN"
    assert data["safety_score"] == 95.0
    assert len(data["coordinates"]) == 2
    assert data["coordinates"][0] == [91.7360, 26.1440]


@pytest.mark.asyncio
async def test_get_road_detail_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/roads/non_existent_edge_id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_roads_geojson(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/roads/geojson?min_lat=26.143&min_lon=91.735&max_lat=26.147&max_lon=91.739&limit=50"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) >= 1

    feature = next(f for f in data["features"] if f["id"] == "api_edge_1")
    assert feature["geometry"]["type"] == "LineString"
    assert feature["properties"]["name"] == "Assam Trunk Road"
    assert feature["properties"]["status"] == "UNKNOWN"
    assert feature["properties"]["safety_score"] == 95.0
