"""Server-Sent Events (SSE) broadcaster and Redis Streams consumer.

Connects backend event publishing to authenticated browser clients with
role-based and object-level authorization filtering, heartbeats, and graceful recovery.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.logistics import Trip, Vehicle
from backend.models.users import User

logger = logging.getLogger(__name__)
settings = get_settings()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Subscriber:
    user_id: uuid.UUID
    role: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))
    authorized_vehicle_ids: set[str] = field(default_factory=set)
    authorized_trip_ids: set[str] = field(default_factory=set)


class SSEBroadcaster:
    """Manages real-time SSE subscriptions and consumes from Redis Streams."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.redis_url
        self._subscribers: dict[asyncio.Queue, Subscriber] = {}
        self._consumer_task: asyncio.Task | None = None
        self._running: bool = False
        self._seen_event_ids: deque[str] = deque(maxlen=2000)
        self._seen_ids_set: set[str] = set()

    async def start(self) -> None:
        """Starts the background Redis Streams consumer loop."""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._redis_consumer_loop())
        logger.info("SSEBroadcaster Redis Streams consumer loop started.")

    async def stop(self) -> None:
        """Stops the background consumer loop and clears subscribers."""
        self._running = False
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        self._subscribers.clear()
        logger.info("SSEBroadcaster stopped.")

    async def subscribe(self, user: User, session: AsyncSession) -> Subscriber:
        """Registers a new authenticated subscriber with object-level authorization."""
        subscriber = Subscriber(user_id=user.id, role=user.role)

        if user.role == "driver":
            # 1. Resolve vehicles assigned to this driver
            veh_res = await session.execute(
                select(Vehicle.id).where(Vehicle.assigned_driver_id == user.id)
            )
            for vid in veh_res.scalars().all():
                subscriber.authorized_vehicle_ids.add(str(vid))

            # 2. Resolve active trips assigned to this driver
            trip_res = await session.execute(
                select(Trip.id, Trip.vehicle_id).where(
                    Trip.driver_id == user.id,
                    Trip.status.in_(["PLANNED", "IN_TRANSIT", "PAUSED"]),
                )
            )
            for tid, vid in trip_res.all():
                subscriber.authorized_trip_ids.add(str(tid))
                if vid:
                    subscriber.authorized_vehicle_ids.add(str(vid))

        self._subscribers[subscriber.queue] = subscriber

        logger.debug(
            f"Subscriber registered: user={user.id} role={user.role} "
            f"vehicles={subscriber.authorized_vehicle_ids} trips={subscriber.authorized_trip_ids}"
        )
        return subscriber

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Removes a subscriber queue."""
        self._subscribers.pop(queue, None)
        logger.debug("Subscriber unregistered.")

    def _is_authorized(self, sub: Subscriber, event: dict[str, Any]) -> bool:
        """
        Enforces role-based and object-level authorization rules:
        - Admin & Dispatcher: Full corridor-wide visibility.
        - Field Officer: Incident and road network updates.
        - Driver: Incident & road updates (safety awareness), but vehicle & trip updates
          ONLY for their assigned vehicle/trip.
        """
        role = sub.role
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})
        entity_id = str(event.get("entity_id", ""))

        if role in ("admin", "dispatcher"):
            return True

        if role == "field_officer":
            # Field officers receive incident, evidence, road, and alert events
            return event_type.startswith(("incident.", "road.", "evidence.", "alert."))

        if role == "driver":
            # Drivers always receive corridor-wide incident, road, and weather events for road safety
            if event_type.startswith(("incident.", "road.", "weather.")):
                return True

            # For alert events, restrict strictly to driver's user_id or active trip/vehicle
            if event_type.startswith("alert."):
                rec_user_id = str(payload.get("recipient_user_id") or "")
                rec_role = str(payload.get("recipient_role") or "")
                details = payload.get("details") or {}
                ev_trip_id = str(details.get("trip_id") or payload.get("trip_id") or "")
                ev_vehicle_id = str(details.get("vehicle_id") or payload.get("vehicle_id") or "")

                if rec_user_id and rec_user_id == str(sub.user_id):
                    return True
                if ev_trip_id and ev_trip_id in sub.authorized_trip_ids:
                    return True
                if ev_vehicle_id and ev_vehicle_id in sub.authorized_vehicle_ids:
                    return True
                return False

            # For vehicle telemetry updates, restrict strictly to driver's assigned vehicle/trip
            if event_type.startswith("vehicle."):
                ev_vehicle_id = str(payload.get("vehicle_id") or entity_id)
                ev_trip_id = str(payload.get("trip_id") or "")
                if ev_vehicle_id in sub.authorized_vehicle_ids:
                    return True
                if ev_trip_id and ev_trip_id in sub.authorized_trip_ids:
                    return True
                return False

            # For trip events (trip.rerouted, trip.started, trip.completed, etc.)
            if event_type.startswith("trip."):
                ev_trip_id = str(payload.get("trip_id") or entity_id)
                ev_driver_id = str(payload.get("driver_id") or "")
                ev_vehicle_id = str(payload.get("vehicle_id") or "")

                if ev_driver_id and ev_driver_id == str(sub.user_id):
                    # Dynamic enrollment if new trip assigned to driver
                    sub.authorized_trip_ids.add(ev_trip_id)
                    if ev_vehicle_id:
                        sub.authorized_vehicle_ids.add(ev_vehicle_id)
                    return True

                if ev_trip_id in sub.authorized_trip_ids or ev_vehicle_id in sub.authorized_vehicle_ids:
                    return True
                return False

        return False

    def broadcast_event(self, event_data: dict[str, Any]) -> int:
        """
        Broadcasts event to all authorized subscriber queues in memory.
        Deduplicates by event_id to prevent redundant deliveries.
        """
        event_id = event_data.get("event_id")
        if event_id:
            if event_id in self._seen_ids_set:
                return 0
            if len(self._seen_event_ids) >= 2000:
                oldest = self._seen_event_ids.popleft()
                self._seen_ids_set.discard(oldest)
            self._seen_event_ids.append(event_id)
            self._seen_ids_set.add(event_id)

        delivered = 0
        for queue, sub in list(self._subscribers.items()):
            if self._is_authorized(sub, event_data):
                try:
                    queue.put_nowait(event_data)
                    delivered += 1
                except asyncio.QueueFull:
                    logger.warning(f"Subscriber queue full for user {sub.user_id}. Dropping event.")
        return delivered

    async def _redis_consumer_loop(self) -> None:
        """Reads events continuously from Redis Streams and broadcasts them."""
        stream_keys = [
            settings.REDIS_STREAM_INCIDENTS,
            settings.REDIS_STREAM_ROADS,
            settings.REDIS_STREAM_VEHICLES,
            settings.REDIS_STREAM_TRIPS,
            settings.REDIS_STREAM_EVIDENCE,
            settings.REDIS_STREAM_ALERTS,
        ]
        # Start reading new events from Redis
        last_ids = {s: "$" for s in stream_keys}

        while self._running:
            try:
                client = aioredis.from_url(
                    self.redis_url,
                    socket_connect_timeout=2.0,
                    decode_responses=True,
                )
                try:
                    while self._running:
                        entries = await client.xread(last_ids, block=1000, count=50)
                        if not entries:
                            continue

                        for stream_name, messages in entries:
                            for msg_id, data in messages:
                                last_ids[stream_name] = msg_id
                                raw_json = data.get("data")
                                if raw_json:
                                    try:
                                        event_dict = json.loads(raw_json)
                                        self.broadcast_event(event_dict)
                                    except Exception as parse_err:
                                        logger.warning(f"Malformed event in {stream_name}: {parse_err}")
                finally:
                    await client.aclose()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._running:
                    logger.warning(f"Redis Streams consumer reconnecting in 2s: {exc}")
                    await asyncio.sleep(2.0)


# Global singleton instance
_broadcaster: SSEBroadcaster | None = None


def get_sse_broadcaster() -> SSEBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SSEBroadcaster()
    return _broadcaster
