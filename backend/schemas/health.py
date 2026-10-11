"""Health check response schemas."""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class HealthLiveResponse(BaseModel):
    status: str = Field(default="ok", description="Liveness status of the service")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str = "ner-link-api"


class DependencyStatus(BaseModel):
    status: str
    has_postgis: bool | None = None
    postgis_version: str | None = None
    postgresql_version: str | None = None
    ping: bool | None = None
    error: str | None = None


class HealthReadyResponse(BaseModel):
    status: str = Field(description="Readiness status ('ready' or 'not_ready')")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str = "ner-link-api"
    database: DependencyStatus
    redis: DependencyStatus
    ready: bool
