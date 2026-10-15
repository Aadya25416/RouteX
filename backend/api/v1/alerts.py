"""Operational alerts and notifications API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user
from backend.database import get_async_session
from backend.models.audit import Alert
from backend.models.users import User
from backend.schemas.alerts import (
    AlertAcknowledgeResponse,
    AlertListResponse,
    AlertResponse,
)
from backend.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info", "warning"}


def _to_alert_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        recipient_user_id=alert.recipient_user_id,
        recipient_role=alert.recipient_role,
        event_type=alert.event_type,
        severity=alert.severity,
        message=alert.message,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by_id=alert.acknowledged_by_id,
        entity_type=alert.entity_type,
        entity_id=alert.entity_id,
        details=alert.details or {},
        dedup_key=alert.dedup_key,
        created_at=alert.created_at,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    is_acknowledged: bool | None = Query(default=None, description="Filter by acknowledgement state"),
    severity: str | None = Query(default=None, description="Filter by severity: critical, high, medium, low, info"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    entity_type: str | None = Query(default=None, description="Filter by entity type (e.g. trip, incident)"),
    entity_id: str | None = Query(default=None, description="Filter by entity ID"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> AlertListResponse:
    """
    Lists operational alerts visible to the authenticated user.
    - Admins and Dispatchers see corridor-wide alerts, role alerts, and targeted alerts.
    - Drivers see only alerts targeted to their specific user ID.
    """
    if severity and severity.lower() not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity '{severity}'. Must be one of: {sorted(list(VALID_SEVERITIES))}",
        )

    alert_service = AlertService(session=session)
    total, unack_count, items = await alert_service.list_alerts(
        current_user=current_user,
        is_acknowledged=is_acknowledged,
        severity=severity.lower() if severity else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )

    return AlertListResponse(
        total=total,
        unacknowledged_count=unack_count,
        items=[_to_alert_response(item) for item in items],
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertAcknowledgeResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AlertAcknowledgeResponse:
    """
    Acknowledges an alert. Idempotent: returns successfully if already acknowledged.
    Enforces object-level authorization: drivers cannot acknowledge alerts of other users.
    """
    alert_service = AlertService(session=session)
    alert = await alert_service.acknowledge_alert(alert_id=alert_id, current_user=current_user)

    return AlertAcknowledgeResponse(
        id=alert.id,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by_id=alert.acknowledged_by_id,
        message="Alert successfully acknowledged.",
    )
