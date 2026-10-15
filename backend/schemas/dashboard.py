"""Pydantic schemas for real-time operational dashboard metrics."""

from datetime import datetime
from pydantic import BaseModel, Field


class IncidentStatusSummary(BaseModel):
    submitted: int = Field(default=0, description="Unverified reports pending review")
    under_review: int = Field(default=0, description="Reports currently under review")
    confirmed: int = Field(default=0, description="Officially verified incidents")
    resolved: int = Field(default=0, description="Cleared hazards")
    rejected: int = Field(default=0, description="Dismissed false reports")
    total: int = Field(default=0, description="All recorded incidents")
    active_unresolved: int = Field(default=0, description="Submitted, under review, and confirmed incidents")


class IncidentSeveritySummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class RoadStatusSummary(BaseModel):
    open: int = 0
    at_risk: int = 0
    restricted: int = 0
    blocked: int = 0
    unknown: int = 0
    total: int = 0


class VehicleFleetSummary(BaseModel):
    total: int = 0
    available: int = 0
    in_transit: int = 0
    maintenance: int = 0
    inactive: int = 0
    live_tracking_active: int = 0


class TripSummary(BaseModel):
    total: int = 0
    planned: int = 0
    in_transit: int = 0
    paused: int = 0
    completed: int = 0
    cancelled: int = 0
    active_count: int = 0
    recent_reroutes: int = 0


class DeliverySummary(BaseModel):
    total: int = 0
    pending: int = 0
    dispatched: int = 0
    in_transit: int = 0
    delivered: int = 0
    priority_count: int = 0


class AlertSummary(BaseModel):
    total_unacknowledged: int = 0
    critical_unacknowledged: int = 0
    recent_count: int = 0


class DashboardMetricsResponse(BaseModel):
    corridor_name: str
    generated_at: datetime
    incidents: IncidentStatusSummary
    incident_severities: IncidentSeveritySummary
    roads: RoadStatusSummary
    vehicles: VehicleFleetSummary
    trips: TripSummary
    deliveries: DeliverySummary
    alerts: AlertSummary
