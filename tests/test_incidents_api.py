"""Tests for Incident Management API endpoints, validation, idempotency, and RBAC."""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_incident_success(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test valid incident creation by an authorized field officer."""
    payload = {
        "incident_type": "LANDSLIDE",
        "severity": "HIGH",
        "latitude": 26.145,
        "longitude": 91.745,
        "description": "Severe debris block after monsoon rainfall",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "client_report_id": f"client_rpt_{uuid.uuid4().hex[:10]}",
    }

    response = await async_client.post("/api/v1/incidents", json=payload, headers=field_officer_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_type"] == "LANDSLIDE"
    assert data["severity"] == "HIGH"
    assert data["status"] == "SUBMITTED"
    assert data["description"] == payload["description"]
    assert data["latitude"] == pytest.approx(26.145, abs=0.0001)
    assert data["longitude"] == pytest.approx(91.745, abs=0.0001)
    assert data["client_report_id"] == payload["client_report_id"]
    assert "road_associations" in data
    assert "evidence_items" in data


@pytest.mark.asyncio
async def test_create_incident_unauthorized(async_client: AsyncClient):
    """Test incident creation fails without authentication."""
    payload = {
        "incident_type": "FLOOD",
        "severity": "MEDIUM",
        "latitude": 26.15,
        "longitude": 91.75,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    response = await async_client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_incident_invalid_coordinates(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test validation errors for coordinates out of bounds."""
    # Latitude > 90
    bad_lat = {
        "incident_type": "FLOOD",
        "severity": "MEDIUM",
        "latitude": 95.0,
        "longitude": 91.75,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await async_client.post("/api/v1/incidents", json=bad_lat, headers=field_officer_headers)
    assert res.status_code in [400, 422]

    # Longitude > 180
    bad_lon = {
        "incident_type": "FLOOD",
        "severity": "MEDIUM",
        "latitude": 26.15,
        "longitude": 185.0,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    res2 = await async_client.post("/api/v1/incidents", json=bad_lon, headers=field_officer_headers)
    assert res2.status_code in [400, 422]


@pytest.mark.asyncio
async def test_create_incident_invalid_type_or_severity(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test validation errors for unsupported incident type or severity."""
    bad_type = {
        "incident_type": "METEOR_STRIKE",
        "severity": "MEDIUM",
        "latitude": 26.15,
        "longitude": 91.75,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await async_client.post("/api/v1/incidents", json=bad_type, headers=field_officer_headers)
    assert res.status_code == 422

    bad_sev = {
        "incident_type": "FLOOD",
        "severity": "EXTREME_CATASTROPHE",
        "latitude": 26.15,
        "longitude": 91.75,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    res2 = await async_client.post("/api/v1/incidents", json=bad_sev, headers=field_officer_headers)
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_incident_idempotency_same_client_report_id(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test offline retries with identical client_report_id return the existing incident without creating duplicates."""
    idempotency_key = f"offline_sync_{uuid.uuid4().hex}"
    payload = {
        "incident_type": "ROAD_DAMAGE",
        "severity": "MEDIUM",
        "latitude": 26.148,
        "longitude": 91.748,
        "description": "First submission attempt",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "client_report_id": idempotency_key,
    }

    # 1. First submission
    res1 = await async_client.post("/api/v1/incidents", json=payload, headers=field_officer_headers)
    assert res1.status_code == 201
    data1 = res1.json()
    incident_id1 = data1["id"]

    # 2. Repeated retry with same key
    res2 = await async_client.post("/api/v1/incidents", json=payload, headers=field_officer_headers)
    assert res2.status_code in [200, 201]
    data2 = res2.json()
    assert data2["id"] == incident_id1
    assert data2["client_report_id"] == idempotency_key


@pytest.mark.asyncio
async def test_list_and_filter_incidents(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test listing incidents with pagination and filtering."""
    # Create two distinct incidents
    await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "BRIDGE_DAMAGE",
            "severity": "CRITICAL",
            "latitude": 26.16,
            "longitude": 91.76,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "TRAFFIC",
            "severity": "LOW",
            "latitude": 26.17,
            "longitude": 91.77,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )

    # Filter by type=BRIDGE_DAMAGE
    res = await async_client.get("/api/v1/incidents?type=BRIDGE_DAMAGE", headers=field_officer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["incident_type"] == "BRIDGE_DAMAGE"

    # Filter by severity=CRITICAL
    res_sev = await async_client.get("/api/v1/incidents?severity=CRITICAL", headers=field_officer_headers)
    assert res_sev.status_code == 200
    data_sev = res_sev.json()
    for item in data_sev["items"]:
        assert item["severity"] == "CRITICAL"

    # Pagination
    res_page = await async_client.get("/api/v1/incidents?limit=2&offset=0", headers=field_officer_headers)
    assert res_page.status_code == 200
    data_page = res_page.json()
    assert len(data_page["items"]) <= 2


@pytest.mark.asyncio
async def test_get_incident_detail_and_not_found(async_client: AsyncClient, field_officer_headers: dict[str, str]):
    """Test retrieving existing incident detail and handling non-existent ID."""
    # Create
    create_res = await async_client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "OTHER",
            "severity": "LOW",
            "latitude": 26.142,
            "longitude": 91.742,
            "description": "Oil spill near market",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=field_officer_headers,
    )
    inc_id = create_res.json()["id"]

    # Retrieve
    get_res = await async_client.get(f"/api/v1/incidents/{inc_id}", headers=field_officer_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == inc_id

    # Non-existent ID
    fake_id = str(uuid.uuid4())
    res_404 = await async_client.get(f"/api/v1/incidents/{fake_id}", headers=field_officer_headers)
    assert res_404.status_code == 404
