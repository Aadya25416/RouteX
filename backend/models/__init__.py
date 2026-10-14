"""Database models for NER-LINK."""

from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.models.users import User
from backend.models.districts import District
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus
from backend.models.incidents import (
    Incident,
    IncidentEvidence,
    IncidentRoadAssociation,
    IncidentType,
    IncidentSeverity,
    IncidentStatus,
    AssociationType,
    AssessedImpact,
    IncidentSource,
)
from backend.models.logistics import (
    Vehicle,
    VehicleLocation,
    Delivery,
    Trip,
    VehicleStatus,
    CargoType,
    DeliveryPriority,
    DeliveryStatus,
    TripStatus,
)
from backend.models.routing import RouteRecommendation, RouteMode
from backend.models.risk import RiskPrediction
from backend.models.observations import (
    WeatherObservation,
    SatelliteEvent,
    TrafficObservation,
    SatelliteIngestionLog,
)
from backend.models.audit import Alert, AuditLog

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "District",
    "RoadNode",
    "RoadSegment",
    "RoadSegmentState",
    "RoadStatus",
    "Incident",
    "IncidentEvidence",
    "IncidentRoadAssociation",
    "IncidentType",
    "IncidentSeverity",
    "IncidentStatus",
    "AssociationType",
    "AssessedImpact",
    "IncidentSource",
    "Vehicle",
    "VehicleLocation",
    "Delivery",
    "Trip",
    "VehicleStatus",
    "CargoType",
    "DeliveryPriority",
    "DeliveryStatus",
    "TripStatus",
    "RouteRecommendation",
    "RouteMode",
    "RiskPrediction",
    "WeatherObservation",
    "SatelliteEvent",
    "TrafficObservation",
    "SatelliteIngestionLog",
    "Alert",
    "AuditLog",
]

