"""Tests for GPS Location Ingestion and Tracking (Step 5)."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.fixture
async def registered_vehicle(async_client: AsyncClient, dispatcher_headers: dict[str, str]):
    unique_reg = f"AS-01-{uuid.uuid4().hex[:6].upper()}"
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": unique_reg, "vehicle_type": "truck", "status": "AVAILABLE"},
        headers=dispatcher_headers,
    )
    assert v_res.status_code == 201
    return v_res.json()


@pytest.mark.asyncio
async def test_gps_location_ingestion_and_monotonicity(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    registered_vehicle: dict,
):
    veh_id = registered_vehicle["id"]
    now = datetime.now(timezone.utc)

    # 1. Ingest initial GPS location
    payload1 = {
        "latitude": 26.14365,
        "longitude": 91.74172,
        "speed_kmh": 45.0,
        "heading_deg": 180.0,
        "source": "gps_driver_app",
        "recorded_at": now.isoformat(),
    }
    res1 = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=payload1, headers=driver_headers)
    assert res1.status_code == 201, res1.text
    data1 = res1.json()
    assert data1["vehicle_id"] == veh_id
    assert data1["matched_segment_id"] is not None
    assert data1["snapping_distance_m"] is not None
    assert data1["speed_kmh"] == 45.0

    # 2. Get latest location
    latest_res = await async_client.get(f"/api/v1/vehicles/{veh_id}/location", headers=driver_headers)
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert latest_data["vehicle_id"] == veh_id
    assert latest_data["latitude"] == pytest.approx(26.14365, abs=1e-4)

    # 3. Reject out-of-order GPS update (timestamp older than current latest)
    payload_old = {
        "latitude": 26.14300,
        "longitude": 91.74180,
        "speed_kmh": 40.0,
        "recorded_at": (now - timedelta(minutes=5)).isoformat(),
    }
    old_res = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=payload_old, headers=driver_headers)
    assert old_res.status_code == 400
    assert "Out-of-order GPS update rejected" in old_res.json()["detail"]

    # 4. Ingest newer GPS location
    payload2 = {
        "latitude": 26.14249,
        "longitude": 91.74202,
        "speed_kmh": 50.0,
        "heading_deg": 190.0,
        "source": "gps_driver_app",
        "recorded_at": (now + timedelta(seconds=30)).isoformat(),
    }
    res2 = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=payload2, headers=driver_headers)
    assert res2.status_code == 201

    # 5. Retrieve history
    hist_res = await async_client.get(f"/api/v1/vehicles/{veh_id}/locations", headers=driver_headers)
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] >= 2


@pytest.mark.asyncio
async def test_gps_validation_rules(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    registered_vehicle: dict,
):
    veh_id = registered_vehicle["id"]
    now = datetime.now(timezone.utc)

    # Invalid latitude
    bad_lat = {
        "latitude": 95.0,
        "longitude": 91.74,
        "recorded_at": now.isoformat(),
    }
    res = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=bad_lat, headers=driver_headers)
    assert res.status_code == 422

    # Unauthenticated update
    good_payload = {
        "latitude": 26.14,
        "longitude": 91.74,
        "recorded_at": now.isoformat(),
    }
    unauth_res = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=good_payload)
    assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_gps_ingestion_survives_redis_outage(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    registered_vehicle: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    veh_id = registered_vehicle["id"]
    now = datetime.now(timezone.utc)

    # Monkeypatch settings to point to invalid redis port
    from backend.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "REDIS_PORT", 59999)

    payload = {
        "latitude": 26.14365,
        "longitude": 91.74172,
        "speed_kmh": 35.0,
        "recorded_at": (now + timedelta(minutes=10)).isoformat(),
    }
    # Ingestion must succeed by writing to PostgreSQL despite Redis being unavailable
    res = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=payload, headers=driver_headers)
    assert res.status_code == 201
    assert res.json()["vehicle_id"] == veh_id
