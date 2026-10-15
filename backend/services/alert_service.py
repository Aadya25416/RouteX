"""Operational Alert and Notification Service.

Handles creation, deduplication, listing, and acknowledgement of actionable
operational alerts across incidents, road disruptions, and trip reroutes.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit import Alert
from backend.models.base import utc_now
from backend.models.users import User
from backend.schemas.alerts import AlertCreate
from backend.services.events import EventPublisher

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing actionable system alerts with RBAC and real-time delivery."""

    def __init__(self, session: AsyncSession, event_publisher: EventPublisher | None = None):
        self.session = session
        self.publisher = event_publisher or EventPublisher()

    async def create_alert(
        self,
        event_type: str,
        severity: str,
        message: str,
        recipient_role: str | None = None,
        recipient_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        dedup_key: str | None = None,
    ) -> Alert:
        """
        Creates an actionable alert with deduplication protection.
        Reliably commits the alert to PostgreSQL and dispatches alert.created event.
        """
        # Deduplication check
        if dedup_key:
            existing_res = await self.session.execute(
                select(Alert).where(Alert.dedup_key == dedup_key)
            )
            existing = existing_res.scalar_one_or_none()
            if existing:
                logger.info(f"Duplicate alert skipped for dedup_key='{dedup_key}' (alert {existing.id})")
                return existing

        alert = Alert(
            id=uuid.uuid4(),
            event_type=event_type,
            severity=severity.lower(),
            message=message,
            recipient_role=recipient_role,
            recipient_user_id=recipient_user_id,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details=details or {},
            dedup_key=dedup_key,
            is_acknowledged=False,
            created_at=utc_now(),
        )

        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        # Dispatch real-time SSE & Redis Streams event
        try:
            await self.publisher.publish_event(
                event_type="alert.created",
                entity_id=str(alert.id),
                payload={
                    "alert_id": str(alert.id),
                    "event_type": alert.event_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "recipient_role": alert.recipient_role,
                    "recipient_user_id": str(alert.recipient_user_id) if alert.recipient_user_id else None,
                    "entity_type": alert.entity_type,
                    "entity_id": alert.entity_id,
                    "details": alert.details or {},
                    "is_acknowledged": alert.is_acknowledged,
                    "created_at": alert.created_at.isoformat(),
                },
            )
        except Exception as exc:
            # Resilient fallback: notification failure must not break business transaction
            logger.warning(f"Failed to publish alert.created event for alert {alert.id}: {exc}")

        return alert

    async def list_alerts(
        self,
        current_user: User,
        is_acknowledged: bool | None = None,
        severity: str | None = None,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, int, list[Alert]]:
        """
        Lists alerts with role-based and object-level authorization filtering.
        Admins/dispatchers see corridor-wide & role-targeted alerts.
        Drivers see only alerts targeted to their specific user ID.
        """
        query = select(Alert)

        # Role-based visibility isolation
        if current_user.role == "driver":
            # Drivers may ONLY read alerts explicitly targeted to them
            query = query.where(Alert.recipient_user_id == current_user.id)
        else:
            # Dispatchers & Admins see corridor-wide alerts, role-matching alerts, or targeted alerts
            query = query.where(
                (Alert.recipient_user_id == current_user.id)
                | (Alert.recipient_role.in_(["dispatcher", "admin"]))
                | (Alert.recipient_role.is_(None))
            )

        if is_acknowledged is not None:
            query = query.where(Alert.is_acknowledged == is_acknowledged)

        if severity:
            query = query.where(Alert.severity == severity.lower())

        if event_type:
            query = query.where(Alert.event_type == event_type)

        if entity_type:
            query = query.where(Alert.entity_type == entity_type)

        if entity_id:
            query = query.where(Alert.entity_id == str(entity_id))

        # Total matching count
        total_query = select(func.count()).select_from(query.subquery())
        total_res = await self.session.execute(total_query)
        total = total_res.scalar_one() or 0

        # Total unacknowledged count in the current user's visibility scope
        unack_query = select(Alert).where(Alert.is_acknowledged == False)  # noqa: E712
        if current_user.role == "driver":
            unack_query = unack_query.where(Alert.recipient_user_id == current_user.id)
        else:
            unack_query = unack_query.where(
                (Alert.recipient_user_id == current_user.id)
                | (Alert.recipient_role.in_(["dispatcher", "admin"]))
                | (Alert.recipient_role.is_(None))
            )
        unack_count_query = select(func.count()).select_from(unack_query.subquery())
        unack_res = await self.session.execute(unack_count_query)
        unack_count = unack_res.scalar_one() or 0

        # Execute paginated query
        paged_query = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(paged_query)
        items = list(res.scalars().all())

        return total, unack_count, items

    async def acknowledge_alert(self, alert_id: uuid.UUID, current_user: User) -> Alert:
        """
        Acknowledges an alert. Idempotent: returns existing state if already acknowledged.
        Enforces object-level authorization: drivers cannot acknowledge alerts of other users.
        """
        res = await self.session.execute(select(Alert).where(Alert.id == alert_id))
        alert = res.scalar_one_or_none()

        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert with ID '{alert_id}' was not found.",
            )

        # Authorization check
        if current_user.role == "driver":
            if alert.recipient_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Drivers may only acknowledge alerts specifically assigned to them.",
                )

        # Idempotent: if already acknowledged, return immediately
        if alert.is_acknowledged:
            return alert

        alert.is_acknowledged = True
        alert.acknowledged_at = utc_now()
        alert.acknowledged_by_id = current_user.id

        await self.session.commit()
        await self.session.refresh(alert)

        # Broadcast acknowledgment event
        try:
            await self.publisher.publish_event(
                event_type="alert.acknowledged",
                entity_id=str(alert.id),
                payload={
                    "alert_id": str(alert.id),
                    "acknowledged_by_id": str(current_user.id),
                    "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    "event_type": alert.event_type,
                    "severity": alert.severity,
                    "entity_type": alert.entity_type,
                    "entity_id": alert.entity_id,
                },
            )
        except Exception as exc:
            logger.warning(f"Failed to publish alert.acknowledged event: {exc}")

        return alert
