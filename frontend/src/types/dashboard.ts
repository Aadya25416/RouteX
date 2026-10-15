/**
 * Operational Dashboard Metrics Types
 * Matches the backend DashboardMetricsResponse schema.
 */

export interface IncidentStatusSummary {
  submitted: number;
  under_review: number;
  confirmed: number;
  resolved: number;
  rejected: number;
  total: number;
  active_unresolved: number;
}

export interface IncidentSeveritySummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface RoadStatusSummary {
  open: number;
  at_risk: number;
  restricted: number;
  blocked: number;
  unknown: number;
  total: number;
}

export interface VehicleFleetSummary {
  total: number;
  available: number;
  in_transit: number;
  maintenance: number;
  inactive: number;
  live_tracking_active: number;
}

export interface TripSummary {
  total: number;
  planned: number;
  in_transit: number;
  paused: number;
  completed: number;
  cancelled: number;
  active_count: number;
  recent_reroutes: number;
}

export interface DeliverySummary {
  total: number;
  pending: number;
  dispatched: number;
  in_transit: number;
  delivered: number;
  priority_count: number;
}

export interface AlertSummary {
  total_unacknowledged: number;
  critical_unacknowledged: number;
  recent_count: number;
}

export interface DashboardMetricsResponse {
  corridor_name: string;
  generated_at: string;
  incidents: IncidentStatusSummary;
  incident_severities: IncidentSeveritySummary;
  roads: RoadStatusSummary;
  vehicles: VehicleFleetSummary;
  trips: TripSummary;
  deliveries: DeliverySummary;
  alerts: AlertSummary;
}
