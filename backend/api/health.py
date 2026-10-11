"""Health and readiness check endpoints."""

from fastapi import APIRouter, Response, status
from backend.database import check_database_connection, check_redis_connection
from backend.schemas.health import DependencyStatus, HealthLiveResponse, HealthReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health/live", response_model=HealthLiveResponse)
async def health_live() -> HealthLiveResponse:
    """Liveness probe indicating the web application process is responsive."""
    return HealthLiveResponse()


@router.get("/health/ready", response_model=HealthReadyResponse)
async def health_ready(response: Response) -> HealthReadyResponse:
    """Readiness probe verifying PostgreSQL connectivity with PostGIS and Redis availability."""
    db_info = await check_database_connection()
    redis_info = await check_redis_connection()

    db_ready = db_info.get("status") == "connected" and db_info.get("has_postgis") is True
    redis_ready = redis_info.get("status") == "connected" and redis_info.get("ping") is True

    is_ready = db_ready and redis_ready

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthReadyResponse(
        status="ready" if is_ready else "not_ready",
        database=DependencyStatus(**db_info),
        redis=DependencyStatus(**redis_info),
        ready=is_ready,
    )
