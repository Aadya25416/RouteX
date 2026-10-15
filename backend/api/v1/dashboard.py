"""Corridor operational dashboard summary endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user
from backend.database import get_async_session
from backend.models.users import User
from backend.schemas.dashboard import DashboardMetricsResponse
from backend.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardMetricsResponse:
    """
    Returns real-time aggregated metrics for the corridor operational dashboard.
    All metrics are calculated strictly from live database state.
    """
    dashboard_service = DashboardService(session=session)
    return await dashboard_service.get_metrics(current_user=current_user)
