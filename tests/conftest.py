"""Pytest fixtures and configuration."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import Settings, get_settings
from backend.database import AsyncSessionLocal, sync_engine
from backend.main import app


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Async database session fixture."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def field_officer_headers() -> dict[str, str]:
    return {"X-User-Role": "field_officer", "X-User-Email": "officer1@nerlink.org"}


@pytest.fixture
def dispatcher_headers() -> dict[str, str]:
    return {"X-User-Role": "dispatcher", "X-User-Email": "dispatcher1@nerlink.org"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-User-Role": "admin", "X-User-Email": "admin1@nerlink.org"}


@pytest.fixture
def driver_headers() -> dict[str, str]:
    return {"X-User-Role": "driver", "X-User-Email": "driver1@nerlink.org"}

