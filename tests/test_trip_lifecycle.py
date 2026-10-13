"""Tests for Trip Lifecycle and Coupled Vehicle-Delivery State Transitions (Step 3)."""

import uuid
import pytest
from httpx import AsyncClient


@pytest.fixture
async def sample_vehicle_and_delivery(async_client: AsyncClient, dispatcher_headers: dict[str, str]):
    # 1. Create available vehicle
    v_reg = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    v_code = f"TRK-{uuid.uuid4().hex[:4].upper()}"
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": v_reg, "vehicle_code": v_code, "vehicle_type": "truck", "capacity_kg": 5000.0},
        headers=dispatcher_headers,
    )
    assert v_res.status_code == 201
    veh_data = v_res.json()

    # 2. Create pending delivery
    d_code = f"DEL-{uuid.uuid4().hex[:6].upper()}"
    d_res = await async_client.post(
        "/api/v1/deliveries",
        json={
            "tracking_code": d_code,
            "cargo_type": "FOOD",
            "cargo_class": "rations",
            "priority": "HIGH",
            "origin_address": "Guwahati Central Depot",
            "origin_lat": 26.14365,
            "origin_lon": 91.74172,
            "destination_address": "Dispur Substation",
            "destination_lat": 26.14249,
            "destination_lon": 91.74202,
        },
        headers=dispatcher_headers,
    )
    assert d_res.status_code == 201
    deliv_data = d_res.json()

    return veh_data, deliv_data


@pytest.mark.asyncio
async def test_full_trip_lifecycle_and_coupled_states(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
    sample_vehicle_and_delivery: tuple[dict, dict],
):
    veh, deliv = sample_vehicle_and_delivery

    # 1. Create & assign trip
    trip_payload = {
        "vehicle_id": veh["id"],
        "delivery_id": deliv["id"],
        "routing_mode": "SHORTEST_DISTANCE",
    }
    create_trip_res = await async_client.post("/api/v1/trips", json=trip_payload, headers=dispatcher_headers)
    assert create_trip_res.status_code == 201, create_trip_res.text
    trip = create_trip_res.json()
    trip_id = trip["id"]
    assert trip["status"] == "PLANNED"
    assert trip["current_route_id"] is not None
    assert trip["estimated_distance_m"] > 0
    assert trip["estimated_duration_s"] > 0

    # Verify vehicle and delivery states updated to ASSIGNED
    v_check = await async_client.get(f"/api/v1/vehicles/{veh['id']}", headers=dispatcher_headers)
    assert v_check.json()["status"] == "ASSIGNED"

    d_check = await async_client.get(f"/api/v1/deliveries/{deliv['id']}", headers=dispatcher_headers)
    assert d_check.json()["status"] == "ASSIGNED"

    # Conflicting assignment: Cannot assign already assigned vehicle or delivery
    conflict_res = await async_client.post("/api/v1/trips", json=trip_payload, headers=dispatcher_headers)
    assert conflict_res.status_code == 409

    # 2. Invalid transition: Cannot pause PLANNED trip
    bad_pause = await async_client.post(f"/api/v1/trips/{trip_id}/pause", headers=driver_headers)
    assert bad_pause.status_code == 400

    # 3. Start trip (PLANNED -> IN_TRANSIT)
    start_res = await async_client.post(f"/api/v1/trips/{trip_id}/start", headers=driver_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_TRANSIT"
    assert start_res.json()["started_at"] is not None

    # Check vehicle and delivery transitioned to IN_TRANSIT
    v_check2 = await async_client.get(f"/api/v1/vehicles/{veh['id']}", headers=dispatcher_headers)
    assert v_check2.json()["status"] == "IN_TRANSIT"

    d_check2 = await async_client.get(f"/api/v1/deliveries/{deliv['id']}", headers=dispatcher_headers)
    assert d_check2.json()["status"] == "IN_TRANSIT"

    # 4. Pause trip (IN_TRANSIT -> PAUSED)
    pause_res = await async_client.post(f"/api/v1/trips/{trip_id}/pause", json={"reason": "Driver rest"}, headers=driver_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"
    assert pause_res.json()["paused_at"] is not None

    # 5. Resume trip (PAUSED -> IN_TRANSIT)
    resume_res = await async_client.post(f"/api/v1/trips/{trip_id}/resume", headers=driver_headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "IN_TRANSIT"

    # 6. Complete trip (IN_TRANSIT -> COMPLETED)
    complete_res = await async_client.post(f"/api/v1/trips/{trip_id}/complete", headers=driver_headers)
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "COMPLETED"
    assert complete_res.json()["completed_at"] is not None

    # Delivery must be DELIVERED and vehicle must be released to AVAILABLE
    v_final = await async_client.get(f"/api/v1/vehicles/{veh['id']}", headers=dispatcher_headers)
    assert v_final.json()["status"] == "AVAILABLE"

    d_final = await async_client.get(f"/api/v1/deliveries/{deliv['id']}", headers=dispatcher_headers)
    assert d_final.json()["status"] == "DELIVERED"

    # 7. Invalid transition: Cannot restart completed trip
    restart_res = await async_client.post(f"/api/v1/trips/{trip_id}/start", headers=driver_headers)
    assert restart_res.status_code == 400


@pytest.mark.asyncio
async def test_trip_cancellation_releases_vehicle(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    sample_vehicle_and_delivery: tuple[dict, dict],
):
    veh, deliv = sample_vehicle_and_delivery

    trip_payload = {"vehicle_id": veh["id"], "delivery_id": deliv["id"]}
    create_res = await async_client.post("/api/v1/trips", json=trip_payload, headers=dispatcher_headers)
    assert create_res.status_code == 201
    trip_id = create_res.json()["id"]

    # Cancel trip
    cancel_res = await async_client.post(
        f"/api/v1/trips/{trip_id}/cancel",
        json={"cancellation_reason": "Order cancelled by hospital dispatcher"},
        headers=dispatcher_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["cancellation_reason"] == "Order cancelled by hospital dispatcher"

    # Vehicle returned to AVAILABLE and delivery returned to PENDING
    v_chk = await async_client.get(f"/api/v1/vehicles/{veh['id']}", headers=dispatcher_headers)
    assert v_chk.json()["status"] == "AVAILABLE"

    d_chk = await async_client.get(f"/api/v1/deliveries/{deliv['id']}", headers=dispatcher_headers)
    assert d_chk.json()["status"] == "PENDING"
