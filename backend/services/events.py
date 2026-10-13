"""Event publishing and audit logging service."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.audit import AuditLog

logger = logging.getLogger(__name__)
settings = get_settings()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventPublisher:
    """Publishes standardized domain events to Redis Streams with resilient fallback."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.redis_url

    async def publish_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, Any],
        stream_name: str | None = None,
    ) -> str | None:
        """
        Publishes a standardized event to Redis Streams.
        A Redis connection failure or outage logs a warning but never raises or aborts transactions.
        """
        event_id = str(uuid.uuid4())
        stream = stream_name or (
            settings.REDIS_STREAM_ROADS if event_type.startswith("road.") else settings.REDIS_STREAM_INCIDENTS
        )

        event_data = {
            "event_id": event_id,
            "schema_version": "1.0",
            "event_type": event_type,
            "entity_id": str(entity_id),
            "timestamp": utc_now_iso(),
            "source": "nerlink.backend",
            "payload": payload,
        }

        try:
            client = aioredis.from_url(
                self.redis_url,
                socket_connect_timeout=1.5,
                decode_responses=True,
            )
            # Add to Redis Stream with approximate maxlen to prevent unbounded memory growth
            await client.xadd(
                stream,
                {"data": json.dumps(event_data, default=str)},
                maxlen=10000,
                approximate=True,
            )
            await client.aclose()
            logger.debug(f"Published event {event_type} [{event_id}] to stream {stream}")
            return event_id
        except Exception as exc:
            # Resilient fallback: temporary Redis failure must not fail the committed record
            logger.warning(
                f"Failed to publish event {event_type} [{event_id}] to Redis Stream '{stream}': {exc}"
            )
            return None


def record_audit_log(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Creates an immutable audit log entry in PostgreSQL."""
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details or {},
    )
    session.add(audit_entry)
    return audit_entry
