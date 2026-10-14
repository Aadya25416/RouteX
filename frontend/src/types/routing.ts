/**
 * TypeScript types for Route Planning matching backend/schemas/routing.py
 */

export type RouteMode = "FASTEST_SAFE" | "SHORTEST_DISTANCE";

export interface SnappedPoint {
  node_id: string;
  distance_m: number;
  latitude: number;
  longitude: number;
}

export interface SafetySummary {
  safety_status: "VERIFIED_SAFE" | "UNVERIFIED" | "AT_RISK" | "RESTRICTED" | string;
  meets_safety_policy: boolean;
  unknown_segment_count: number;
  at_risk_segment_count: number;
  restricted_segment_count: number;
  blocked_segment_count: number;
  unknown_segments: string[];
  at_risk_segments: string[];
  restricted_segments: string[];
  disclaimer?: string | null;
  reasons: string[];
}

export interface RouteRecommendationResponse {
  id?: string | null;
  trip_id?: string | null;
  mode: RouteMode;
  snapped_origin: SnappedPoint;
  snapped_destination: SnappedPoint;
  ordered_node_ids: string[];
  ordered_segment_ids: string[];
  route_geojson: {
    type: string;
    coordinates: [number, number][];
  };
  distance_m: number;
  eta_seconds: number;
  meets_safety_policy: boolean;
  safety_summary: SafetySummary;
  avoided_hazard_count: number;
  reason?: string | null;
  computed_at: string;
}

export interface RoutePlanRequest {
  origin_lat: number;
  origin_lon: number;
  destination_lat: number;
  destination_lon: number;
  mode: RouteMode;
  trip_id?: string | null;
  max_snapping_distance_m?: number;
  require_verified_safe?: boolean;
}

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface LocationSuggestion {
  name: string;
  category?: string;
  coords: Coordinates;
}
