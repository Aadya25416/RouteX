"""Tests for Vehicle and Delivery Management APIs (Step 1 & Step 2)."""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_vehicle_success_and_conflict(async_client: AsyncClient, dispatcher_headers: dict[str, str]):
    unique_reg = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    unique_code = f"TRK-{uuid.uuid4().hex[:4].upper()}"

    payload = {
        "registration_number": unique_reg,
        "vehicle_code": unique_code,
        "vehicle_type": "heavy_truck",
        "capacity_kg": 15000.0,
        "status": "AVAILABLE",
    }

    # 1. Register vehicle successfully
    response = await async_client.post("/api/v1/vehicles", json=payload, headers=dispatcher_headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["registration_number"] == unique_reg
    assert data["vehicle_code"] == unique_code
    assert data["vehicle_type"] == "heavy_truck"
    assert data["capacity_kg"] == 15000.0
    assert data["status"] == "AVAILABLE"
    assert data["is_active"] is True
    veh_id = data["id"]

    # 2. Duplicate registration number -> 409 Conflict
    dup_reg_payload = {
        "registration_number": unique_reg,
        "vehicle_code": f"TRK-{uuid.uuid4().hex[:4].upper()}",
        "vehicle_type": "pickup",
    }
    dup_res = await async_client.post("/api/v1/vehicles", json=dup_reg_payload, headers=dispatcher_headers)
    assert dup_res.status_code == 409

    # 3. Duplicate vehicle code -> 409 Conflict
    dup_code_payload = {
        "registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}",
        "vehicle_code": unique_code,
        "vehicle_type": "pickup",
    }
    dup_code_res = await async_client.post("/api/v1/vehicles", json=dup_code_payload, headers=dispatcher_headers)
    assert dup_code_res.status_code == 409

    # 4. Get vehicle
    get_res = await async_client.get(f"/api/v1/vehicles/{veh_id}", headers=dispatcher_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == veh_id


@pytest.mark.asyncio
async def test_vehicle_rbac_and_update(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    # Non-dispatcher/admin cannot register vehicle
    payload = {
        "registration_number": f"AS-02-{uuid.uuid4().hex[:6].upper()}",
        "vehicle_type": "van",
    }
    forbidden_res = await async_client.post("/api/v1/vehicles", json=payload, headers=driver_headers)
    assert forbidden_res.status_code == 403

    # Dispatcher can register
    create_res = await async_client.post("/api/v1/vehicles", json=payload, headers=dispatcher_headers)
    assert create_res.status_code == 201
    veh_id = create_res.json()["id"]

    # Update vehicle status
    update_payload = {"status": "MAINTENANCE", "capacity_kg": 2500.0}
    update_res = await async_client.patch(f"/api/v1/vehicles/{veh_id}", json=update_payload, headers=dispatcher_headers)
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "MAINTENANCE"
    assert update_res.json()["capacity_kg"] == 2500.0


@pytest.mark.asyncio
async def test_create_and_list_deliveries(async_client: AsyncClient, dispatcher_headers: dict[str, str], driver_headers: dict[str, str]):
    code = f"DEL-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "tracking_code": code,
        "cargo_type": "MEDICINE",
        "cargo_class": "cold_chain",
        "description": "Essential medical vaccines for regional health centers",
        "priority": "CRITICAL",
        "origin_address": "Guwahati Medical College Depot",
        "origin_name": "GMC Depot",
        "origin_lat": 26.14365,
        "origin_lon": 91.74172,
        "destination_address": "Dispur Primary Health Centre",
        "destination_name": "Dispur PHC",
        "destination_lat": 26.14249,
        "destination_lon": 91.74202,
    }

    # 1. Driver cannot create delivery
    forbidden = await async_client.post("/api/v1/deliveries", json=payload, headers=driver_headers)
    assert forbidden.status_code == 403

    # 2. Dispatcher creates delivery
    res = await async_client.post("/api/v1/deliveries", json=payload, headers=dispatcher_headers)
    assert res.status_code == 201, res.text
    deliv = res.json()
    assert deliv["tracking_code"] == code
    assert deliv["cargo_type"] == "MEDICINE"
    assert deliv["priority"] == "CRITICAL"
    assert deliv["status"] == "PENDING"
    assert deliv["origin_lat"] == pytest.approx(26.14365, abs=1e-4)
    deliv_id = deliv["id"]

    # 3. Duplicate tracking code -> 409
    dup_res = await async_client.post("/api/v1/deliveries", json=payload, headers=dispatcher_headers)
    assert dup_res.status_code == 409

    # 4. Invalid coordinates -> 422
    bad_payload = dict(payload, tracking_code=f"DEL-{uuid.uuid4().hex[:6].upper()}", origin_lat=95.0)
    bad_res = await async_client.post("/api/v1/deliveries", json=bad_payload, headers=dispatcher_headers)
    assert bad_res.status_code == 422

    # 5. List deliveries
    list_res = await async_client.get("/api/v1/deliveries?cargo_type=MEDICINE", headers=dispatcher_headers)
    assert list_res.status_code == 200
    assert any(item["id"] == deliv_id for item in list_res.json()["items"])

    # 6. Update delivery
    update_res = await async_client.patch(
        f"/api/v1/deliveries/{deliv_id}",
        json={"priority": "HIGH", "description": "Updated vaccine batch"},
        headers=dispatcher_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["priority"] == "HIGH"
