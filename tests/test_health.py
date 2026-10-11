"""Tests for health check and readiness endpoints."""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "NER-LINK"
    assert "corridor" in data
    assert "OpenStreetMap" in data["attribution"]


@pytest.mark.asyncio
async def test_health_live(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["service"] == "ner-link-api"


@pytest.mark.asyncio
async def test_health_ready_success(async_client: AsyncClient):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["database"]["status"] == "connected"
    assert data["database"]["has_postgis"] is True
    assert data["redis"]["status"] == "connected"
    assert data["redis"]["ping"] is True


@pytest.mark.asyncio
async def test_health_ready_db_failure(async_client: AsyncClient):
    with patch(
        "backend.api.health.check_database_connection",
        new=AsyncMock(return_value={"status": "disconnected", "has_postgis": False, "error": "Connection refused"}),
    ):
        response = await async_client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["ready"] is False
        assert data["database"]["status"] == "disconnected"


@pytest.mark.asyncio
async def test_health_ready_redis_failure(async_client: AsyncClient):
    with patch(
        "backend.api.health.check_redis_connection",
        new=AsyncMock(return_value={"status": "disconnected", "ping": False, "error": "Redis timeout"}),
    ):
        response = await async_client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["ready"] is False
        assert data["redis"]["status"] == "disconnected"
