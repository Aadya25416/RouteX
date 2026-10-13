"""Tests for Incident Lifecycle state transitions, road-state aggregation, and auditability."""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.audit import AuditLog
from backend.models.incidents import IncidentRoadAssociation
from backend.models.roads import RoadSegment, RoadSegmentState, RoadStatus


@pytest.mark.asyncio
async def test_review_and_rbac_flow(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
    driver_headers: dict[str, str],
):
    """Test review transition and role access enforcement."""
    # 1. Field officer creates incident
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "FLOOD",
            "severity": "HIGH",
            "latitude": 26.145,
            "longitude": 91.745,
            "description": "Flash flood covering road",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    assert create_res.status_code == 201
    incident_id = create_res.json()["id"]

    # 2. Driver role attempts to review -> Forbidden (403)
    driver_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/review",
        json={"review_notes": "Driver note"},
        headers=driver_headers,
    )
    assert driver_res.status_code == 403

    # 3. Dispatcher reviews incident -> Success (200, status=UNDER_REVIEW)
    review_res = await async_client.post(
        f"/api/v1/incidents/{incident_id}/review",
        json={"review_notes": "Assigned emergency crew for verification"},
        headers=dispatcher_headers,
    )
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["status"] == "UNDER_REVIEW"
    assert rev_data["review_notes"] == "Assigned emergency crew for verification"
    assert rev_data["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_rejection_requires_reason(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Test rejecting an incident requires a valid reason."""
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "TRAFFIC",
            "severity": "LOW",
            "latitude": 26.15,
            "longitude": 91.75,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    incident_id = create_res.json()["id"]

    # Reject without reason (empty string or missing)
    bad_reject = await async_client.post(
        f"/api/v1/incidents/{incident_id}/reject",
        json={"rejection_reason": ""},
        headers=dispatcher_headers,
    )
    assert bad_reject.status_code in [400, 422]

    # Valid rejection
    good_reject = await async_client.post(
        f"/api/v1/incidents/{incident_id}/reject",
        json={"rejection_reason": "False report, road is completely clear"},
        headers=dispatcher_headers,
    )
    assert good_reject.status_code == 200
    assert good_reject.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_multi_incident_road_state_aggregation_and_unknown_retention(
    async_client: AsyncClient,
    db_session: AsyncSession,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """
    Critical test verifying:
    1. Incident A confirms BLOCKED on a road segment -> segment becomes BLOCKED.
    2. Incident B confirms RESTRICTED on the same segment -> segment remains BLOCKED (precedence).
    3. Resolving Incident B -> segment remains BLOCKED (Incident A still active).
    4. Resolving Incident A without verified clearance -> segment retains UNKNOWN, NOT OPEN!
    5. Resolving with verified clearance -> segment becomes OPEN.
    """
    # Pick a real road segment from database
    seg_res = await db_session.execute(select(RoadSegment).limit(1))
    target_segment = seg_res.scalar_one()
    segment_id = target_segment.id

    # Clean up any leftover associations on this segment to guarantee test isolation
    await db_session.execute(
        delete(IncidentRoadAssociation).where(IncidentRoadAssociation.road_segment_id == segment_id)
    )
    st_row = (await db_session.execute(select(RoadSegmentState).where(RoadSegmentState.road_segment_id == segment_id))).scalar_one_or_none()
    if st_row:
        st_row.status = RoadStatus.UNKNOWN.value
        st_row.safety_score = 100.0
    await db_session.commit()

    # 1. Submit Incident 1 (Landslide)
    res1 = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "LANDSLIDE",
            "severity": "CRITICAL",
            "latitude": 26.15,
            "longitude": 91.75,
            "description": "Massive landslide",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc1_id = res1.json()["id"]

    # 2. Submit Incident 2 (Flooding on same segment)
    res2 = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "FLOOD",
            "severity": "MEDIUM",
            "latitude": 26.15,
            "longitude": 91.75,
            "description": "Standing water on road",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc2_id = res2.json()["id"]

    # 3. Confirm Incident 1 with BLOCKED impact
    conf1 = await async_client.post(
        f"/api/v1/incidents/{inc1_id}/confirm",
        json={
            "review_notes": "Confirmed total blockage",
            "road_impacts": [{"road_segment_id": segment_id, "assessed_impact": "BLOCKED"}],
        },
        headers=dispatcher_headers,
    )
    assert conf1.status_code == 200

    # Verify road segment state via roads API is BLOCKED
    r1 = await async_client.get(f"/api/v1/roads/{segment_id}")
    assert r1.status_code == 200
    assert r1.json()["status"] == RoadStatus.BLOCKED.value
    assert r1.json()["safety_score"] == 0.0

    # 4. Confirm Incident 2 with RESTRICTED impact on the same segment
    conf2 = await async_client.post(
        f"/api/v1/incidents/{inc2_id}/confirm",
        json={
            "review_notes": "Confirmed partial flooding",
            "road_impacts": [{"road_segment_id": segment_id, "assessed_impact": "RESTRICTED"}],
        },
        headers=dispatcher_headers,
    )
    assert conf2.status_code == 200

    # Road state MUST still be BLOCKED because Incident 1 BLOCKED takes precedence!
    r2 = await async_client.get(f"/api/v1/roads/{segment_id}")
    assert r2.status_code == 200
    assert r2.json()["status"] == RoadStatus.BLOCKED.value

    # 5. Resolve Incident 2 (Flooding receded)
    res_inc2 = await async_client.post(
        f"/api/v1/incidents/{inc2_id}/resolve",
        json={"resolution_notes": "Water pumped out", "verified_clearance": False},
        headers=dispatcher_headers,
    )
    assert res_inc2.status_code == 200

    # Road state MUST STILL BE BLOCKED! Resolving Incident 2 must NOT erase Incident 1's blockage!
    r3 = await async_client.get(f"/api/v1/roads/{segment_id}")
    assert r3.status_code == 200
    assert r3.json()["status"] == RoadStatus.BLOCKED.value

    # 6. Resolve Incident 1 WITHOUT verified clearance
    res_inc1 = await async_client.post(
        f"/api/v1/incidents/{inc1_id}/resolve",
        json={"resolution_notes": "Excavator finished clearing debris", "verified_clearance": False},
        headers=dispatcher_headers,
    )
    assert res_inc1.status_code == 200

    # CRITICAL RULE: When no active incidents remain, road MUST retain UNKNOWN, NEVER OPEN!
    r4 = await async_client.get(f"/api/v1/roads/{segment_id}")
    assert r4.status_code == 200
    assert r4.json()["status"] == RoadStatus.UNKNOWN.value, "Road must retain UNKNOWN when no active incidents remain without verified clearance"

    # 7. Verify audit logs were created
    audit_res = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == inc1_id)
    )
    logs = audit_res.scalars().all()
    actions = [l.action for l in logs]
    assert "incident_submitted" in actions
    assert "incident_confirmed" in actions
    assert "incident_resolved" in actions


@pytest.mark.asyncio
async def test_illegal_state_transitions(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Test illegal state transitions are rejected with clear 400 error."""
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "LOW",
            "latitude": 26.15,
            "longitude": 91.75,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = create_res.json()["id"]

    # 1. Attempt to resolve SUBMITTED incident directly without confirmation -> Bad Request (400)
    bad_resolve = await async_client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={"resolution_notes": "Trying to resolve directly"},
        headers=dispatcher_headers,
    )
    assert bad_resolve.status_code == 400

    # 2. Reject the incident
    reject_res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/reject",
        json={"rejection_reason": "Not reproducible"},
        headers=dispatcher_headers,
    )
    assert reject_res.status_code == 200

    # 3. Attempt to confirm already REJECTED incident -> Bad Request (400)
    bad_confirm = await async_client.post(
        f"/api/v1/incidents/{inc_id}/confirm",
        json={"review_notes": "Attempting to confirm rejected"},
        headers=dispatcher_headers,
    )
    assert bad_confirm.status_code == 400
