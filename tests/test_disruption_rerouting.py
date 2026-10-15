"""Tests for Disruption-Aware Route Validation and Rerouting (Step 6)."""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.roads import RoadSegmentState, RoadStatus


@pytest.fixture(autouse=True)
async def cleanup_road_states(db_session: AsyncSession):
    """Ensures road segment states are clean before and after disruption tests."""
    yield
    await db_session.execute(
        update(RoadSegmentState).values(status=RoadStatus.UNKNOWN.value, safety_score=100.0)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_disruption_triggers_reroute_or_clear_failure(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dispatcher_headers: dict[str, str],
    field_officer_headers: dict[str, str],
):
    # 1. Create vehicle
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    assert v_res.status_code == 201
    veh_id = v_res.json()["id"]

    # 2. Create delivery
    d_res = await async_client.post(
        "/api/v1/deliveries",
        json={
            "tracking_code": f"DEL-{uuid.uuid4().hex[:6].upper()}",
            "cargo_type": "MEDICINE",
            "priority": "CRITICAL",
            "origin_address": "Guwahati Central Depot",
            "origin_lat": 26.14365,
            "origin_lon": 91.74172,
            "destination_address": "Dispur Clinic",
            "destination_lat": 26.14249,
            "destination_lon": 91.74202,
        },
        headers=dispatcher_headers,
    )
    assert d_res.status_code == 201
    deliv_id = d_res.json()["id"]

    # 3. Create trip
    trip_res = await async_client.post(
        "/api/v1/trips",
        json={"vehicle_id": veh_id, "delivery_id": deliv_id, "routing_mode": "SHORTEST_DISTANCE"},
        headers=dispatcher_headers,
    )
    assert trip_res.status_code == 201
    trip = trip_res.json()
    trip_id = trip["id"]
    initial_route_id = trip["current_route_id"]
    assert initial_route_id is not None

    # Get route details
    route_res = await async_client.get(f"/api/v1/routes/{initial_route_id}", headers=dispatcher_headers)
    assert route_res.status_code == 200
    route_data = route_res.json()
    traversed_segments = route_data["ordered_segment_ids"]
    assert len(traversed_segments) > 0
    disrupted_edge = traversed_segments[0]

    # 4. Create another trip that does NOT use this edge (or a dummy vehicle/delivery) to test unaffected trips
    v_res2 = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    veh_id2 = v_res2.json()["id"]

    d_res2 = await async_client.post(
        "/api/v1/deliveries",
        json={
            "tracking_code": f"DEL-{uuid.uuid4().hex[:6].upper()}",
            "cargo_type": "FOOD",
            "origin_address": "Depot 2",
            "origin_lat": 26.14365,
            "origin_lon": 91.74172,
            "destination_address": "Depot 2",
            "destination_lat": 26.14365,
            "destination_lon": 91.74172,  # same node
        },
        headers=dispatcher_headers,
    )
    trip_res2 = await async_client.post(
        "/api/v1/trips",
        json={"vehicle_id": veh_id2, "delivery_id": d_res2.json()["id"]},
        headers=dispatcher_headers,
    )
    unaffected_trip_id = trip_res2.json()["id"]
    unaffected_initial_route_id = trip_res2.json()["current_route_id"]

    # 5. Submit an incident and confirm it, setting disrupted_edge to BLOCKED
    now = datetime.now(timezone.utc)
    inc_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "LANDSLIDE",
            "severity": "CRITICAL",
            "latitude": 26.14365,
            "longitude": 91.74172,
            "observed_at": now.isoformat(),
            "description": "Massive landslide blocking main route",
        },
        headers=field_officer_headers,
    )
    assert inc_res.status_code == 201
    inc_id = inc_res.json()["id"]

    # Confirm incident with verified road impact
    confirm_payload = {
        "review_notes": "Confirmed complete blockage by field unit",
        "road_impacts": [
            {
                "road_segment_id": disrupted_edge,
                "assessed_impact": "BLOCKED",
            }
        ],
    }
    confirm_res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/confirm",
        json=confirm_payload,
        headers=dispatcher_headers,
    )
    assert confirm_res.status_code == 200

    # 6. Check affected trip state: Route should either be rerouted or marked with clear failure
    trip_after = await async_client.get(f"/api/v1/trips/{trip_id}", headers=dispatcher_headers)
    assert trip_after.status_code == 200
    trip_after_data = trip_after.json()

    if trip_after_data["current_route_id"] != initial_route_id:
        # Successfully rerouted!
        new_route_res = await async_client.get(f"/api/v1/routes/{trip_after_data['current_route_id']}", headers=dispatcher_headers)
        assert new_route_res.status_code == 200
        new_segments = new_route_res.json()["ordered_segment_ids"]
        assert disrupted_edge not in new_segments, "New route must avoid the newly blocked segment"
    else:
        # If no alternative route existed, cancellation reason / disruption note must be recorded
        assert trip_after_data["cancellation_reason"] is not None
        assert "blocked" in trip_after_data["cancellation_reason"].lower() or "disrupted" in trip_after_data["cancellation_reason"].lower()

    # 7. Check unaffected trip: Its route must remain unchanged!
    unaffected_trip_after = await async_client.get(f"/api/v1/trips/{unaffected_trip_id}", headers=dispatcher_headers)
    assert unaffected_trip_after.status_code == 200
    assert unaffected_trip_after.json()["current_route_id"] == unaffected_initial_route_id


@pytest.mark.asyncio
async def test_manual_trip_reroute_endpoint(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    # 1. Create vehicle
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    veh_id = v_res.json()["id"]

    # 2. Create delivery
    d_res = await async_client.post(
        "/api/v1/deliveries",
        json={
            "tracking_code": f"DEL-{uuid.uuid4().hex[:6].upper()}",
            "cargo_type": "CONSTRUCTION_MATERIALS",
            "priority": "NORMAL",
            "origin_address": "Guwahati Central Depot",
            "origin_lat": 26.14365,
            "origin_lon": 91.74172,
            "destination_address": "Dispur Clinic",
            "destination_lat": 26.14249,
            "destination_lon": 91.74202,
        },
        headers=dispatcher_headers,
    )
    deliv_id = d_res.json()["id"]

    # 3. Create trip
    trip_res = await async_client.post(
        "/api/v1/trips",
        json={"vehicle_id": veh_id, "delivery_id": deliv_id},
        headers=dispatcher_headers,
    )
    trip_id = trip_res.json()["id"]

    # 4. Trigger manual reroute
    reroute_res = await async_client.post(f"/api/v1/trips/{trip_id}/reroute", headers=dispatcher_headers)
    assert reroute_res.status_code == 200
    data = reroute_res.json()
    assert data["trip_id"] == trip_id
    assert data["status"] in ["REROUTED", "NO_SAFE_ROUTE"]
