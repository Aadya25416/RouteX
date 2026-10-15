/**
 * Operational Alerts and Notifications Types
 * Defined to match FastAPI AlertResponse and AlertListResponse schemas.
 */

export type AlertSeverity = "critical" | "high" | "warning" | "medium" | "low" | "info";

export interface AlertItem {
  id: string;
  recipient_user_id: string | null;
  recipient_role: string | null;
  event_type: string;
  severity: AlertSeverity;
  message: string;
  is_acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  dedup_key: string | null;
  created_at: string;
}

export interface AlertListResponse {
  total: number;
  unacknowledged_count: number;
  items: AlertItem[];
}

export interface AlertAcknowledgeResponse {
  id: string;
  is_acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by_id: string | null;
  message: string;
}
