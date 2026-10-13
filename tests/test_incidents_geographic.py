"""Tests for PostGIS spatial road matching, search radius, unmatched incidents, and multi-segment associations."""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.roads import RoadSegment


@pytest.mark.asyncio
async def test_nearby_candidate_road_matching(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test incident submitted near known road segments returns suggested candidate segments with distances."""
    # Guwahati core coordinates where imported road network exists
    res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "ROAD_DAMAGE",
            "severity": "HIGH",
            "latitude": 26.15,
            "longitude": 91.75,
            "description": "Potholes on road near Guwahati",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "search_radius_m": 500.0,
        },
        headers=field_officer_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["road_associations"]) > 0
    # Ensure distances are computed and sorted ascending
    distances = [a["distance_m"] for a in data["road_associations"]]
    assert distances == sorted(distances)
    # Check that association_type is SUGGESTED (not verified yet)
    for assoc in data["road_associations"]:
        assert assoc["association_type"] == "SUGGESTED"
        assert assoc["assessed_impact"] is None
        assert assoc["road_segment_id"] is not None


@pytest.mark.asyncio
async def test_no_road_within_search_radius_explicit_unmatched(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """Test incident far from any road or with tiny radius records as unmatched and does not snap to distant roads."""
    # Remote point or very tiny search radius (10 meters) far from imported segments
    res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "OTHER",
            "severity": "LOW",
            "latitude": 26.01,  # Far south outside Guwahati core imported bbox
            "longitude": 91.01,
            "description": "Remote wilderness incident",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "search_radius_m": 50.0,
        },
        headers=field_officer_headers,
    )
    assert res.status_code == 201
    data = res.json()
    # Explicit unmatched status: no road associations suggested, road_segment_id is null
    assert len(data["road_associations"]) == 0
    assert data["road_segment_id"] is None


@pytest.mark.asyncio
async def test_multi_segment_incident_confirmation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """Test an incident affecting multiple distinct road segments can be confirmed with distinct impacts."""
    # Fetch two distinct segments from DB
    seg_res = await db_session.execute(select(RoadSegment).limit(2))
    segments = seg_res.scalars().all()
    assert len(segments) >= 2
    seg1_id, seg2_id = segments[0].id, segments[1].id

    # Create incident
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "FLOOD",
            "severity": "HIGH",
            "latitude": 26.15,
            "longitude": 91.75,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = create_res.json()["id"]

    # Confirm with 2 segments: seg1 is BLOCKED, seg2 is RESTRICTED
    confirm_res = await async_client.post(
        f"/api/v1/incidents/{inc_id}/confirm",
        json={
            "review_notes": "Flooding spans multiple segments across intersection",
            "road_impacts": [
                {"road_segment_id": seg1_id, "assessed_impact": "BLOCKED"},
                {"road_segment_id": seg2_id, "assessed_impact": "RESTRICTED"},
            ],
        },
        headers=dispatcher_headers,
    )
    assert confirm_res.status_code == 200
    data = confirm_res.json()
    verified_assocs = {a["road_segment_id"]: a["assessed_impact"] for a in data["road_associations"]}
    assert verified_assocs[seg1_id] == "BLOCKED"
    assert verified_assocs[seg2_id] == "RESTRICTED"
