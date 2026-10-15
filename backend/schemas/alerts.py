"""Pydantic schemas for operational alerts and notifications."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    event_type: str = Field(description="Alert event classification, e.g. disruption.trip_affected, trip.rerouted")
    severity: str = Field(default="info", description="critical, high, medium, low, info")
    message: str = Field(min_length=1, max_length=2000)
    recipient_role: str | None = None
    recipient_user_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] | None = None
    dedup_key: str | None = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    recipient_user_id: uuid.UUID | None = None
    recipient_role: str | None = None
    event_type: str
    severity: str
    message: str
    is_acknowledged: bool
    acknowledged_at: datetime | None = None
    acknowledged_by_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] | None = None
    dedup_key: str | None = None
    created_at: datetime


class AlertListResponse(BaseModel):
    total: int
    unacknowledged_count: int
    items: list[AlertResponse]


class AlertAcknowledgeResponse(BaseModel):
    id: uuid.UUID
    is_acknowledged: bool
    acknowledged_at: datetime | None = None
    acknowledged_by_id: uuid.UUID | None = None
    message: str
