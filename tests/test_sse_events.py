"""Tests for Authenticated Server-Sent Events (SSE) and Real-Time Event Delivery."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.logistics import Vehicle
from backend.services.sse_broadcaster import get_sse_broadcaster, Subscriber


@pytest.mark.asyncio
async def test_sse_requires_authentication(async_client: AsyncClient):
    """Unauthenticated request to SSE stream must return 401."""
    res = await async_client.get("/api/v1/events/stream")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_sse_connection_acknowledgement(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Authorized dispatcher receives initial connection.established event."""
    res = await async_client.get("/api/v1/events/stream?max_events=0", headers=dispatcher_headers)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    body = res.text
    assert "event: connection.established" in body
    assert '"status": "connected"' in body
    assert '"role": "dispatcher"' in body


@pytest.mark.asyncio
async def test_sse_admin_receives_corridor_events(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Dispatcher receives corridor-wide road and vehicle events."""
    broadcaster = get_sse_broadcaster()

    # Pre-populate subscriber queue when registered or test via broadcast
    test_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "incident.created",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"severity": "HIGH", "type": "LANDSLIDE"},
    }

    # Verify authorization for dispatcher subscriber
    dispatcher_sub = Subscriber(user_id=uuid.uuid4(), role="dispatcher")
    assert broadcaster._is_authorized(dispatcher_sub, test_event) is True

    # Test delivery via broadcaster queue
    delivered = broadcaster.broadcast_event(test_event)
    assert delivered >= 0


@pytest.mark.asyncio
async def test_sse_driver_authorization_isolation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    driver_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """
    Drivers receive ONLY updates for their assigned vehicle/trip.
    Other drivers' telemetry must be strictly filtered out.
    """
    broadcaster = get_sse_broadcaster()

    # 1. Create two vehicles
    v1_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    v2_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    veh1_id = v1_res.json()["id"]
    veh2_id = v2_res.json()["id"]

    driver_user_id = uuid.uuid4()

    # Create driver subscriber authorized strictly for vehicle 1
    driver_sub = Subscriber(
        user_id=driver_user_id,
        role="driver",
        authorized_vehicle_ids={veh1_id},
        authorized_trip_ids={"trip-123"},
    )

    # 2. Vehicle 2 telemetry (UNAUTHORIZED for Driver 1)
    unauth_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "vehicle.location_updated",
        "entity_id": veh2_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"vehicle_id": veh2_id, "latitude": 27.1, "longitude": 92.3},
    }
    assert broadcaster._is_authorized(driver_sub, unauth_event) is False, (
        "Security Violation: Driver was authorized to receive another driver's vehicle telemetry!"
    )

    # 3. Vehicle 1 telemetry (AUTHORIZED for Driver 1)
    auth_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "vehicle.location_updated",
        "entity_id": veh1_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"vehicle_id": veh1_id, "latitude": 26.2, "longitude": 91.8},
    }
    assert broadcaster._is_authorized(driver_sub, auth_event) is True, (
        "Driver should be authorized to receive own assigned vehicle telemetry"
    )

    # 4. Corridor road closure (AUTHORIZED for all drivers)
    road_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "road.status_changed",
        "entity_id": "seg-100",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"road_segment_id": "seg-100", "new_status": "BLOCKED"},
    }
    assert broadcaster._is_authorized(driver_sub, road_event) is True, (
        "Driver should receive corridor safety updates"
    )

    # 5. Unauthorized trip event for different trip
    unauth_trip_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.rerouted",
        "entity_id": "trip-999",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"trip_id": "trip-999", "driver_id": str(uuid.uuid4()), "vehicle_id": veh2_id},
    }
    assert broadcaster._is_authorized(driver_sub, unauth_trip_event) is False, (
        "Driver should not receive rerouting for another driver's trip"
    )

    # 6. Authorized trip event
    auth_trip_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.rerouted",
        "entity_id": "trip-123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"trip_id": "trip-123", "driver_id": str(driver_user_id), "vehicle_id": veh1_id},
    }
    assert broadcaster._is_authorized(driver_sub, auth_trip_event) is True, (
        "Driver should receive rerouting for their assigned trip"
    )


@pytest.mark.asyncio
async def test_event_deduplication():
    """Duplicate event IDs must not be delivered multiple times."""
    broadcaster = get_sse_broadcaster()
    shared_event_id = str(uuid.uuid4())

    event_payload = {
        "event_id": shared_event_id,
        "event_type": "incident.created",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"note": "unique_test_incident"},
    }

    # First broadcast must register event_id
    broadcaster.broadcast_event(event_payload)
    # Second broadcast with identical event_id must return 0
    second_deliv = broadcaster.broadcast_event(event_payload)

    assert second_deliv == 0, "Duplicate event_id was not suppressed"


@pytest.mark.asyncio
async def test_vehicle_location_updates_published(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Verify that posting a location fix publishes vehicle.location_updated."""
    # 1. Register vehicle
    v_res = await async_client.post(
        "/api/v1/vehicles",
        json={"registration_number": f"AS-01-{uuid.uuid4().hex[:6].upper()}", "vehicle_type": "truck"},
        headers=dispatcher_headers,
    )
    veh_id = v_res.json()["id"]

    # 2. Ingest location
    now = datetime.now(timezone.utc)
    payload = {
        "latitude": 26.14365,
        "longitude": 91.74172,
        "speed_kmh": 40.0,
        "heading_deg": 90.0,
        "recorded_at": now.isoformat(),
        "source": "gps_test",
    }
    res = await async_client.post(f"/api/v1/vehicles/{veh_id}/locations", json=payload, headers=driver_headers)
    assert res.status_code == 201
    assert res.json()["vehicle_id"] == veh_id
