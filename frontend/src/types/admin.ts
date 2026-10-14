/**
 * RouteX / NER-LINK — System Admin Dashboard Types
 * Defined to match the Admin Workflow and FastAPI backend schemas.
 */

export interface AdminSummaryMetrics {
  totalSegments: number;
  openSegments: number;
  atRiskSegments: number;
  restrictedSegments: number;
  blockedSegments: number;
  unknownSegments: number;
  pendingIncidents: number;
  activeUsers: number;
  isLive: boolean;
}

export type AdminUserRole = "admin" | "field_officer" | "driver" | "dispatcher";

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: AdminUserRole;
  status: "Active" | "Inactive";
  createdAt: string;
  lastActive: string;
}

export type AdminIncidentStatus = "SUBMITTED" | "UNDER_REVIEW" | "CONFIRMED" | "REJECTED" | "RESOLVED";

export interface AdminIncidentItem {
  id: string;
  type: "LANDSLIDE" | "ROAD_COLLAPSE" | "FLASH_FLOOD" | "BRIDGE_DAMAGE" | "OTHER";
  location: string;
  coordinates: [number, number]; // [lng, lat]
  reportedBy: string;
  reporterRole: "Driver" | "Field Officer" | "Citizen";
  timeAgo: string;
  timestamp: string;
  status: AdminIncidentStatus;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  description: string;
  roadSegmentId?: string;
  reviewNotes?: string;
}

export interface SystemHealthItem {
  name: string;
  status: "Connected" | "Degraded" | "Disconnected" | "Configured";
  details: string;
  lastPing: string;
  isHealthy: boolean;
}

export interface DataSourceItem {
  id: string;
  name: string;
  type: string;
  lastImport: string;
  status: "Success" | "Syncing" | "Error" | "Connected";
  coverage: string;
  notes: string;
}

export interface PlannedRouteOption {
  id: string;
  name: string;
  distanceKm: number;
  durationFormatted: string;
  safetyScore: number;
  riskSummary: string;
  isRecommended: boolean;
  coordinates: [number, number][];
}

export interface DeliveryConsignment {
  id: string;
  origin: string;
  destination: string;
  driver: string;
  vehicle: string;
  status: "In Progress" | "Completed" | "Delayed" | "Assigned";
  etaOrCompleted: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
}
