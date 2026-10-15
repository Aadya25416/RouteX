"""Tests for Priority 2: Alerts Generation, APIs, and Live Dashboard Integration."""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit import Alert
from backend.models.logistics import (
    Delivery,
    DeliveryPriority,
    DeliveryStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleStatus,
)
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus
from backend.models.users import User
from backend.services.alert_service import AlertService
from backend.services.dashboard_service import DashboardService


@pytest.fixture(autouse=True)
async def cleanup_road_states(db_session: AsyncSession):
    """Ensures road segment states are clean before and after disruption tests."""
    await db_session.execute(
        update(RoadSegmentState).values(status=RoadStatus.UNKNOWN.value, safety_score=100.0)
    )
    await db_session.commit()
    yield
    await db_session.execute(
        update(RoadSegmentState).values(status=RoadStatus.UNKNOWN.value, safety_score=100.0)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_alert_creation_and_deduplication(db_session: AsyncSession):
    """Verifies alert creation persists in DB and deduplication key prevents duplicate entries."""
    alert_service = AlertService(session=db_session)
    dedup = f"test:dedup:{uuid.uuid4()}"

    alert1 = await alert_service.create_alert(
        event_type="test.event",
        severity="high",
        message="Test alert message 1",
        recipient_role="dispatcher",
        entity_type="test",
        entity_id="123",
        dedup_key=dedup,
    )
    assert alert1.id is not None
    assert alert1.dedup_key == dedup
    assert alert1.is_acknowledged is False

    # Retry creation with identical dedup_key
    alert2 = await alert_service.create_alert(
        event_type="test.event",
        severity="high",
        message="Test alert message 2 - duplicate",
        recipient_role="dispatcher",
        entity_type="test",
        entity_id="123",
        dedup_key=dedup,
    )

    assert alert2.id == alert1.id
    assert alert2.message == alert1.message


@pytest.mark.asyncio
async def test_critical_incident_and_confirmation_generates_alert(
    async_client: AsyncClient,
    db_session: AsyncSession,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Verifies that creating and confirming critical incidents generates alerts without error."""
    # 1. Create a critical incident
    client_rep_id = f"cli-crit-{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "client_report_id": client_rep_id,
            "incident_type": "LANDSLIDE",
            "severity": "CRITICAL",
            "latitude": 26.14365,
            "longitude": 91.74172,
            "description": "Massive landslide blocking major freight passage.",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert create_res.status_code == 201
    inc_data = create_res.json()
    inc_id = inc_data["id"]

    # Check alert was created for critical incident
    al_res = await db_session.execute(
        select(Alert).where(Alert.dedup_key == f"alert:incident_created:{inc_id}")
    )
    alert = al_res.scalar_one_or_none()
    assert alert is not None
    assert alert.severity == "critical"
    assert alert.entity_type == "incident"
    assert alert.entity_id == str(inc_id)

    # 2. Confirm incident
    # Get associated road segments if any
    road_impacts = []
    if inc_data.get("road_associations"):
        for assoc in inc_data["road_associations"]:
            road_impacts.append({
                "road_segment_id": assoc["road_segment_id"],
                "assessed_impact": "BLOCKED",
            })

    confirm_res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/confirm",
        json={"road_impacts": road_impacts, "review_notes": "Confirmed critical blockage."},
        headers=dispatcher_headers,
    )
    assert confirm_res.status_code == 200

    # Verify confirmation alert
    conf_alert_res = await db_session.execute(
        select(Alert).where(Alert.dedup_key == f"alert:incident_confirmed:{inc_id}")
    )
    conf_alert = conf_alert_res.scalar_one_or_none()
    assert conf_alert is not None
    assert conf_alert.entity_id == str(inc_id)


@pytest.mark.asyncio
async def test_trip_reroute_generates_alert(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dispatcher_headers: dict[str, str],
):
    """Verifies that rerouting an active trip generates actionable reroute alerts."""
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
            "priority": "HIGH",
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
    t_res = await async_client.post(
        "/api/v1/trips",
        json={"vehicle_id": veh_id, "delivery_id": deliv_id},
        headers=dispatcher_headers,
    )
    assert t_res.status_code == 201
    trip_id = t_res.json()["id"]

    # 4. Trigger reroute
    reroute_res = await async_client.post(
        f"/api/v1/trips/{trip_id}/reroute",
        json={"reason": "Preventative hazard avoidance"},
        headers=dispatcher_headers,
    )
    assert reroute_res.status_code == 200

    # Verify reroute alert in DB
    al_res = await db_session.execute(
        select(Alert).where(Alert.entity_type == "trip", Alert.entity_id == str(trip_id))
    )
    trip_alerts = al_res.scalars().all()
    assert len(trip_alerts) >= 1
    reroute_alert = next((a for a in trip_alerts if a.event_type == "trip.rerouted"), None)
    assert reroute_alert is not None
    assert "rerouted" in reroute_alert.message.lower()


@pytest.mark.asyncio
async def test_alerts_api_list_filter_and_rbac(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Verifies listing alerts, filtering by severity and state, and driver role isolation."""
    alert_service = AlertService(session=db_session)

    # Find driver user or provision one
    d_email = f"driver_{uuid.uuid4().hex[:6]}@nerlink.internal"
    driver_headers = {"X-User-Role": "driver", "X-User-Email": d_email}
    # Resolve driver user ID by querying /api/v1/alerts
    driver_list_res = await async_client.get("/api/v1/alerts", headers=driver_headers)
    assert driver_list_res.status_code == 200

    user_res = await db_session.execute(select(User).where(User.email == d_email))
    driver_user = user_res.scalar_one()

    # Seed 1 dispatcher alert and 1 driver-specific alert
    disp_alert = await alert_service.create_alert(
        event_type="corridor.hazard",
        severity="high",
        message="Corridor hazard for dispatchers",
        recipient_role="dispatcher",
        dedup_key=f"disp:{uuid.uuid4()}",
    )
    driver_alert = await alert_service.create_alert(
        event_type="driver.notification",
        severity="warning",
        message="Inspection alert for assigned driver",
        recipient_user_id=driver_user.id,
        dedup_key=f"driver:{uuid.uuid4()}",
    )

    # 1. Dispatcher should see disp_alert
    disp_res = await async_client.get("/api/v1/alerts", headers=dispatcher_headers)
    assert disp_res.status_code == 200
    disp_data = disp_res.json()
    disp_ids = [item["id"] for item in disp_data["items"]]
    assert str(disp_alert.id) in disp_ids

    # 2. Driver must ONLY see driver_alert, NOT disp_alert
    drv_res = await async_client.get("/api/v1/alerts", headers=driver_headers)
    assert drv_res.status_code == 200
    drv_data = drv_res.json()
    drv_ids = [item["id"] for item in drv_data["items"]]
    assert str(driver_alert.id) in drv_ids
    assert str(disp_alert.id) not in drv_ids

    # 3. Filter by severity
    sev_res = await async_client.get("/api/v1/alerts?severity=high", headers=dispatcher_headers)
    assert sev_res.status_code == 200
    for it in sev_res.json()["items"]:
        assert it["severity"] == "high"

    # 4. Invalid severity returns 400
    bad_sev_res = await async_client.get("/api/v1/alerts?severity=INVALID_SEV", headers=dispatcher_headers)
    assert bad_sev_res.status_code == 400

    # 5. Filter by acknowledgement
    unack_res = await async_client.get("/api/v1/alerts?is_acknowledged=false", headers=dispatcher_headers)
    assert unack_res.status_code == 200
    for it in unack_res.json()["items"]:
        assert it["is_acknowledged"] is False


@pytest.mark.asyncio
async def test_alert_acknowledgement_and_object_authorization(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dispatcher_headers: dict[str, str],
):
    """Verifies alert acknowledgement is idempotent and enforces object-level RBAC for drivers."""
    alert_service = AlertService(session=db_session)

    # Create driver 1 and driver 2
    d1_email = f"driver1_{uuid.uuid4().hex[:6]}@nerlink.internal"
    d2_email = f"driver2_{uuid.uuid4().hex[:6]}@nerlink.internal"
    d1_headers = {"X-User-Role": "driver", "X-User-Email": d1_email}
    d2_headers = {"X-User-Role": "driver", "X-User-Email": d2_email}

    # Ping to provision
    await async_client.get("/api/v1/alerts", headers=d1_headers)
    await async_client.get("/api/v1/alerts", headers=d2_headers)

    u1_res = await db_session.execute(select(User).where(User.email == d1_email))
    driver1 = u1_res.scalar_one()

    # Create alert for driver 1
    d1_alert = await alert_service.create_alert(
        event_type="driver.trip_update",
        severity="info",
        message="Assigned route update",
        recipient_user_id=driver1.id,
        dedup_key=f"d1_ack_test:{uuid.uuid4()}",
    )

    # 1. Driver 2 attempts to acknowledge driver 1's alert -> 403 Forbidden
    hack_res = await async_client.post(
        f"/api/v1/alerts/{d1_alert.id}/acknowledge",
        headers=d2_headers,
    )
    assert hack_res.status_code == 403

    # 2. Driver 1 acknowledges own alert -> 200 OK
    ack_res = await async_client.post(
        f"/api/v1/alerts/{d1_alert.id}/acknowledge",
        headers=d1_headers,
    )
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["is_acknowledged"] is True
    assert ack_data["acknowledged_by_id"] == str(driver1.id)

    # 3. Idempotent repeated acknowledgement succeeds
    repeat_res = await async_client.post(
        f"/api/v1/alerts/{d1_alert.id}/acknowledge",
        headers=d1_headers,
    )
    assert repeat_res.status_code == 200
    assert repeat_res.json()["is_acknowledged"] is True

    # 4. Non-existent alert returns 404
    missing_id = uuid.uuid4()
    not_found_res = await async_client.post(
        f"/api/v1/alerts/{missing_id}/acknowledge",
        headers=dispatcher_headers,
    )
    assert not_found_res.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_metrics_endpoint(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    """Verifies that GET /api/v1/dashboard returns database-backed aggregations without fabrication."""
    res = await async_client.get("/api/v1/dashboard", headers=dispatcher_headers)
    assert res.status_code == 200
    data = res.json()

    # Verify top-level structure
    assert "corridor_name" in data
    assert "generated_at" in data
    assert "incidents" in data
    assert "roads" in data
    assert "vehicles" in data
    assert "trips" in data
    assert "deliveries" in data
    assert "alerts" in data

    # Verify incident fields
    inc = data["incidents"]
    assert isinstance(inc["submitted"], int)
    assert isinstance(inc["confirmed"], int)
    assert isinstance(inc["active_unresolved"], int)
    assert inc["active_unresolved"] == inc["submitted"] + inc["under_review"] + inc["confirmed"]

    # Verify road network fields
    roads = data["roads"]
    assert isinstance(roads["open"], int)
    assert isinstance(roads["blocked"], int)
    assert isinstance(roads["total"], int)

    # Verify vehicle fleet fields
    veh = data["vehicles"]
    assert isinstance(veh["total"], int)
    assert isinstance(veh["available"], int)
    assert isinstance(veh["live_tracking_active"], int)

    # Verify trip fields
    trips = data["trips"]
    assert isinstance(trips["total"], int)
    assert isinstance(trips["active_count"], int)
    assert trips["active_count"] == trips["planned"] + trips["in_transit"] + trips["paused"]

    # Verify driver can also access dashboard with role-scoped alert data
    drv_res = await async_client.get("/api/v1/dashboard", headers=driver_headers)
    assert drv_res.status_code == 200
    assert "alerts" in drv_res.json()


@pytest.mark.asyncio
async def test_sse_alert_events_authorization_and_delivery():
    """Verifies that alert events are routed via SSE with object-level driver filtering."""
    from backend.services.sse_broadcaster import Subscriber, get_sse_broadcaster

    broadcaster = get_sse_broadcaster()
    driver1_id = uuid.uuid4()
    driver2_id = uuid.uuid4()

    dispatcher_sub = Subscriber(user_id=uuid.uuid4(), role="dispatcher")
    driver1_sub = Subscriber(user_id=driver1_id, role="driver")
    driver2_sub = Subscriber(user_id=driver2_id, role="driver")

    # Corridor-wide dispatcher alert
    disp_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "alert.created",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "recipient_role": "dispatcher",
            "severity": "critical",
            "message": "Corridor blockage",
        },
    }
    assert broadcaster._is_authorized(dispatcher_sub, disp_event) is True
    assert broadcaster._is_authorized(driver1_sub, disp_event) is False
    assert broadcaster._is_authorized(driver2_sub, disp_event) is False

    # Targeted alert for driver 1
    d1_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "alert.created",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "recipient_user_id": str(driver1_id),
            "recipient_role": "dispatcher",
            "severity": "warning",
            "message": "Your trip route has been recalculated",
        },
    }
    assert broadcaster._is_authorized(dispatcher_sub, d1_event) is True
    assert broadcaster._is_authorized(driver1_sub, d1_event) is True
    assert broadcaster._is_authorized(driver2_sub, d1_event) is False

    # Acknowledged alert event
    ack_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "alert.acknowledged",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "alert_id": str(uuid.uuid4()),
            "recipient_user_id": str(driver1_id),
        },
    }
    assert broadcaster._is_authorized(dispatcher_sub, ack_event) is True
    assert broadcaster._is_authorized(driver1_sub, ack_event) is True
    assert broadcaster._is_authorized(driver2_sub, ack_event) is False

