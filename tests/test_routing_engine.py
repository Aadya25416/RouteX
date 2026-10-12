"""Tests for Routing Engine and Safety Policies (Step 4)."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus


@pytest.mark.asyncio
async def test_route_plan_shortest_distance_and_fastest_safe(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    # Origin and destination coordinates near Guwahati nodes:
    # node_osm_566699656 (26.14365, 91.74172)
    # node_osm_6975529291 (26.14249, 91.74202)
    payload_mode_a = {
        "origin_lat": 26.14365,
        "origin_lon": 91.74172,
        "destination_lat": 26.14249,
        "destination_lon": 91.74202,
        "mode": "SHORTEST_DISTANCE",
        "require_verified_safe": False,
    }

    # 1. Test SHORTEST_DISTANCE
    res_a = await async_client.post("/api/v1/routes/plan", json=payload_mode_a, headers=dispatcher_headers)
    assert res_a.status_code == 200, res_a.text
    data_a = res_a.json()
    assert data_a["mode"] == "SHORTEST_DISTANCE"
    assert data_a["distance_m"] > 0
    assert data_a["eta_seconds"] > 0
    assert len(data_a["ordered_node_ids"]) >= 2
    assert len(data_a["ordered_segment_ids"]) >= 1
    assert data_a["route_geojson"]["type"] == "LineString"
    assert len(data_a["route_geojson"]["coordinates"]) >= 2
    # Check that safety summary discloses unverified edges if UNKNOWN
    assert "safety_summary" in data_a
    assert data_a["safety_summary"]["safety_status"] in ["UNVERIFIED", "VERIFIED_SAFE"]
    route_id = data_a["id"]

    # 2. Test FASTEST_SAFE
    payload_mode_b = dict(payload_mode_a, mode="FASTEST_SAFE")
    res_b = await async_client.post("/api/v1/routes/plan", json=payload_mode_b, headers=dispatcher_headers)
    assert res_b.status_code == 200, res_b.text
    data_b = res_b.json()
    assert data_b["mode"] == "FASTEST_SAFE"
    assert data_b["eta_seconds"] > 0

    # 3. Retrieve persisted route recommendation
    get_res = await async_client.get(f"/api/v1/routes/{route_id}", headers=dispatcher_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == route_id


@pytest.mark.asyncio
async def test_snapping_rejects_distant_coordinates(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    # Coordinate in the middle of the Indian Ocean (far from corridor)
    payload = {
        "origin_lat": 0.0,
        "origin_lon": 80.0,
        "destination_lat": 26.14249,
        "destination_lon": 91.74202,
        "mode": "SHORTEST_DISTANCE",
        "max_snapping_distance_m": 5000.0,
    }
    res = await async_client.post("/api/v1/routes/plan", json=payload, headers=dispatcher_headers)
    assert res.status_code == 400
    assert "too far from a routable road" in res.json()["detail"]


@pytest.mark.asyncio
async def test_blocked_road_strictly_excluded_from_routes(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dispatcher_headers: dict[str, str],
):
    # Pick a segment between two connected nodes
    edge_id = "edge_566699656_6975529291_0"

    # Get or create RoadSegmentState for this edge
    st_res = await db_session.execute(
        select(RoadSegmentState).where(RoadSegmentState.road_segment_id == edge_id)
    )
    seg_state = st_res.scalar_one_or_none()

    orig_status = seg_state.status if seg_state else RoadStatus.UNKNOWN.value

    # Temporarily set to BLOCKED
    if not seg_state:
        seg_state = RoadSegmentState(road_segment_id=edge_id, status=RoadStatus.BLOCKED.value, safety_score=0.0)
        db_session.add(seg_state)
    else:
        seg_state.status = RoadStatus.BLOCKED.value
        seg_state.safety_score = 0.0

    await db_session.commit()

    try:
        payload = {
            "origin_lat": 26.14365,
            "origin_lon": 91.74172,
            "destination_lat": 26.14249,
            "destination_lon": 91.74202,
            "mode": "SHORTEST_DISTANCE",
            "require_verified_safe": False,
        }
        res = await async_client.post("/api/v1/routes/plan", json=payload, headers=dispatcher_headers)

        if res.status_code == 200:
            # If an alternative route was found, verify edge_id is NOT in the chosen route
            data = res.json()
            assert edge_id not in data["ordered_segment_ids"], "BLOCKED edge must never be included in route!"
        else:
            # If no alternative path exists, verify it returned 404 NO_SAFE_ROUTE
            assert res.status_code == 404
            assert "NO_SAFE_ROUTE" in res.json()["detail"]
    finally:
        # Revert segment state
        seg_state.status = orig_status
        await db_session.commit()


@pytest.mark.asyncio
async def test_require_verified_safe_policy_enforcement(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    # When require_verified_safe is True, roads with UNKNOWN status are excluded.
    # Because imported road data is initially UNKNOWN, requiring verified safe edges
    # will cleanly return NO_SAFE_ROUTE unless all traversed edges are verified OPEN.
    payload = {
        "origin_lat": 26.14365,
        "origin_lon": 91.74172,
        "destination_lat": 26.14249,
        "destination_lon": 91.74202,
        "mode": "FASTEST_SAFE",
        "require_verified_safe": True,
    }
    res = await async_client.post("/api/v1/routes/plan", json=payload, headers=dispatcher_headers)
    assert res.status_code == 404
    assert "NO_SAFE_ROUTE" in res.json()["detail"]
    assert "UNKNOWN" in res.json()["detail"]


@pytest.mark.asyncio
async def test_directed_graph_directionality_and_parallel_edges(db_session: AsyncSession):
    from backend.services.routing_engine import RoutingEngine
    from backend.models.routing import RouteMode
    import networkx as nx

    engine = RoutingEngine(db_session)
    G = await engine.load_graph(mode=RouteMode.SHORTEST_DISTANCE)

    # 1. Directed graph: verify it is a MultiDiGraph
    assert isinstance(G, nx.MultiDiGraph)
    assert G.is_directed()

    # 2. Check that parallel edges are preserved with distinct keys
    multiedge_found = False
    for u, v in G.edges():
        if len(G[u][v]) > 1:
            multiedge_found = True
            # Check keys
            assert 0 in G[u][v]
            assert 1 in G[u][v]
            # Ensure both edges have distinct IDs
            assert G[u][v][0]["id"] != G[u][v][1]["id"]
            break

    # If the imported corridor has parallel edges, verify; otherwise assert graph has directed edges
    assert G.number_of_edges() > 0
