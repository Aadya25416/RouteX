"""Tests for system reliability, event publishing resilience during Redis outages, and graph validation regression."""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import sync_engine
from backend.models.roads import RoadSegment
from backend.services.events import EventPublisher
from backend.services.graph_validator import GraphValidator


def test_graph_validator_parallel_edges_parity_regression():
    """
    Regression test for Step 0.5:
    Validates that GraphValidator using nx.MultiDiGraph preserves all parallel directed edges,
    ensuring 1:1 parity between database road_segments count and the reconstructed graph edge count.
    (Previously, simple nx.DiGraph collapsed 1,118 edges down to 1,116).
    """
    with Session(sync_engine) as session:
        db_segment_count = session.execute(select(func.count(RoadSegment.id))).scalar()

    validator = GraphValidator()
    try:
        report = validator.validate()
        assert report["valid"] is True
        # Parity check: edge count in reconstructed graph MUST exactly equal road_segments in DB
        assert report["edge_count"] == db_segment_count, (
            f"Edge count discrepancy! DB has {db_segment_count} segments, "
            f"but GraphValidator reconstructed {report['edge_count']} edges. "
            f"Parallel edges between node pairs must not be dropped."
        )

        # Inspect multigraph directly
        G = validator.build_networkx_graph()
        assert G.number_of_edges() == db_segment_count
    finally:
        validator.close()


@pytest.mark.asyncio
async def test_redis_outage_does_not_fail_incident_creation(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
):
    """
    Reliability test for Step 5:
    A temporary Redis outage or unreachable Redis stream MUST NOT cause incident submission
    to fail or rollback the committed PostgreSQL database record.
    """
    # Simulate Redis connection failure by mocking publish_event failure or unreachable port
    broken_publisher = EventPublisher(redis_url="redis://localhost:59999/0")  # Unreachable port

    with patch("backend.services.incident_service.EventPublisher", return_value=broken_publisher):
        res = await async_client.post(
            "/api/v1/incidents",
            json={
                "incident_type": "LANDSLIDE",
                "severity": "CRITICAL",
                "latitude": 26.15,
                "longitude": 91.75,
                "description": "Incident created during simulated Redis outage",
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
            headers=field_officer_headers,
        )

    # Incident must succeed and commit despite Redis failure!
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "SUBMITTED"
    assert data["incident_type"] == "LANDSLIDE"

    # Confirm it can be retrieved from DB
    get_res = await async_client.get(f"/api/v1/incidents/{data['id']}", headers=field_officer_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == data["id"]
