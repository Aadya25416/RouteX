"""Real-time Server-Sent Events (SSE) streaming endpoint."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import get_current_user, require_roles
from backend.database import get_async_session
from backend.models.users import User
from backend.services.sse_broadcaster import get_sse_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Real-time Events"])


@router.get("/stream")
async def event_stream(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(require_roles(["admin", "dispatcher", "driver", "field_officer"]))],
    max_events: Annotated[int | None, Query(description="Optional limit for automated test execution")] = None,
) -> StreamingResponse:
    """
    Authenticated Server-Sent Events (SSE) stream for real-time telemetry,
    incident status modifications, and automated trip rerouting.

    Enforces role-based and object-level authorization:
    - Admins and dispatchers receive corridor-wide events.
    - Field officers receive corridor incident and road network events.
    - Drivers receive corridor safety/road updates, and telemetry/trip events
      strictly for their assigned active trip and vehicle.
    """
    broadcaster = get_sse_broadcaster()
    subscriber = await broadcaster.subscribe(current_user, session)

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        delivered_count = 0
        try:
            # 1. Connection acknowledgement event
            now_iso = datetime.now(timezone.utc).isoformat()
            ack_payload = {
                "status": "connected",
                "user_id": str(current_user.id),
                "role": current_user.role,
                "timestamp": now_iso,
            }
            yield f"event: connection.established\ndata: {json.dumps(ack_payload)}\n\n"

            # 2. Event stream loop with heartbeat
            while True:
                if max_events is not None and delivered_count >= max_events:
                    break

                try:
                    event_data = await asyncio.wait_for(subscriber.queue.get(), timeout=10.0)
                    event_id = event_data.get("event_id", "")
                    event_type = event_data.get("event_type", "message")
                    yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                    delivered_count += 1
                except asyncio.TimeoutError:
                    if max_events is not None:
                        break
                    # Heartbeat comment to keep HTTP connection alive through reverse proxies
                    ping_time = datetime.now(timezone.utc).isoformat()
                    yield f": ping - {ping_time}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await broadcaster.unsubscribe(subscriber.queue)

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
