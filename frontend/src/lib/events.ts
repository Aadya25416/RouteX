/**
 * Real-Time Event Stream Client for RouteX
 * Uses authenticated fetch with ReadableStream for Server-Sent Events (SSE),
 * automatic JWT refresh retry, exponential reconnect backoff, and deduplication.
 */

import { getAccessToken, api } from "./api";

export interface RouteXEvent<T = any> {
  event_id: string;
  schema_version: string;
  event_type:
    | "connection.established"
    | "vehicle.location_updated"
    | "trip.started"
    | "trip.completed"
    | "trip.rerouted"
    | "trip.route_blocked"
    | "incident.created"
    | "incident.confirmed"
    | "incident.rejected"
    | "incident.resolved"
    | "road.status_changed"
    | "weather.updated"
    | "alert.created";
  entity_id: string;
  timestamp: string;
  source: string;
  payload: T;
}

export interface VehicleLocationPayload {
  vehicle_id: string;
  trip_id?: string | null;
  latitude: number;
  longitude: number;
  speed_kmh?: number | null;
  heading_deg?: number | null;
  matched_segment_id?: string | null;
  snapping_distance_m?: number | null;
  recorded_at: string;
  source?: string;
}

export interface TripReroutedPayload {
  trip_id: string;
  vehicle_id: string;
  driver_id?: string | null;
  previous_route_id?: string;
  new_route_id: string;
  blocked_segments?: string[];
  estimated_distance_m?: number;
  estimated_duration_s?: number;
  reason?: string;
}

export interface RoadStatusChangedPayload {
  road_segment_id: string;
  previous_status: string;
  new_status: string;
  incident_id?: string;
}

export interface IncidentEventPayload {
  incident_id: string;
  type?: string;
  severity?: string;
  latitude?: number;
  longitude?: number;
  reviewer_id?: string;
  affected_segments?: string[];
  reason?: string;
  resolution_notes?: string;
}

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface EventStreamOptions {
  onEvent: (event: RouteXEvent) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  endpoint?: string;
}

/**
 * Connects to the RouteX SSE real-time event stream.
 * Automatically injects the in-memory access token, parses incoming SSE blocks,
 * and maintains resilient connection with bounded backoff.
 *
 * @returns A teardown function that cleanly aborts the connection.
 */
export function connectEventStream(options: EventStreamOptions): () => void {
  const { onEvent, onStatusChange, endpoint = "/api/v1/events/stream" } = options;

  let isAborted = false;
  let abortController: AbortController | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let backoffMs = 1000;
  const maxBackoffMs = 10000;
  const seenEventIds = new Set<string>();

  const notifyStatus = (status: ConnectionStatus) => {
    if (onStatusChange && !isAborted) {
      onStatusChange(status);
    }
  };

  const startConnection = async () => {
    if (isAborted) return;
    notifyStatus("connecting");

    abortController = new AbortController();
    const token = getAccessToken();

    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(endpoint, {
        method: "GET",
        headers,
        credentials: "include", // Attach HttpOnly refresh cookie
        signal: abortController.signal,
      });

      // Handle 401 Unauthorized via single-flight refresh
      if (response.status === 401) {
        const refreshedToken = await api.refresh();
        if (refreshedToken && !isAborted) {
          // Reconnect immediately with refreshed token
          startConnection();
          return;
        } else {
          notifyStatus("error");
          scheduleReconnect();
          return;
        }
      }

      if (!response.ok || !response.body) {
        notifyStatus("error");
        scheduleReconnect();
        return;
      }

      // Connection established
      notifyStatus("connected");
      backoffMs = 1000; // Reset backoff upon successful connection

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!isAborted) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (!block.trim()) continue;

          let eventType = "message";
          let eventDataRaw = "";
          let eventId = "";

          const lines = block.split("\n");
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.replace("event:", "").trim();
            } else if (line.startsWith("data:")) {
              eventDataRaw = line.replace("data:", "").trim();
            } else if (line.startsWith("id:")) {
              eventId = line.replace("id:", "").trim();
            }
          }

          if (eventDataRaw) {
            try {
              const parsedEvent: RouteXEvent = JSON.parse(eventDataRaw);
              if (parsedEvent && parsedEvent.event_id) {
                // Client-side deduplication
                if (seenEventIds.has(parsedEvent.event_id)) {
                  continue;
                }
                seenEventIds.add(parsedEvent.event_id);
                if (seenEventIds.size > 2000) {
                  const oldest = seenEventIds.values().next().value;
                  if (oldest) seenEventIds.delete(oldest);
                }
              }
              onEvent(parsedEvent);
            } catch {
              // Ignore ping or non-JSON payloads
            }
          }
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError" || isAborted) {
        return;
      }
      notifyStatus("disconnected");
      scheduleReconnect();
    }
  };

  const scheduleReconnect = () => {
    if (isAborted) return;
    notifyStatus("disconnected");
    if (reconnectTimeout) clearTimeout(reconnectTimeout);

    reconnectTimeout = setTimeout(() => {
      startConnection();
      backoffMs = Math.min(backoffMs * 1.5, maxBackoffMs);
    }, backoffMs);
  };

  // Initial connection start
  startConnection();

  // Teardown function
  return () => {
    isAborted = true;
    if (abortController) {
      abortController.abort();
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
    }
    notifyStatus("disconnected");
  };
}
