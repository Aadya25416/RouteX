/**
 * TypeScript types strictly mirroring the RouteX / NER-LINK FastAPI schemas.
 * References: backend/schemas/roads.py, backend/schemas/risk.py, and backend/main.py root handler.
 */

export type RoadStatusType = "OPEN" | "AT_RISK" | "RESTRICTED" | "BLOCKED" | "UNKNOWN";

export interface CorridorBBox {
  south: number;
  west: number;
  north: number;
  east: number;
}

export interface BackendInfoResponse {
  name: string;
  version: string;
  environment: string;
  docs?: string;
  corridor: {
    name: string;
    bbox: CorridorBBox;
  };
  attribution: string;
}

export interface RoadFeatureProperties {
  id: string;
  name: string | null;
  road_class: string;
  length_m: number;
  oneway: boolean;
  status: RoadStatusType;
  safety_score: number; // 0–100, where 100 is safer
  disruption_probability: number | null; // 0–1 disruption probability when evaluated
  score_confidence?: number | null;
  score_type?: string;
  model_name?: string | null;
  model_version?: string | null;
  reason_codes?: string[];
  is_stale?: boolean;
  is_unknown?: boolean;
  score_updated_at?: string | null;
  score_valid_until?: string | null;
}

export type RoadGeometry =
  | {
      type: "LineString";
      coordinates: number[][];
    }
  | {
      type: "MultiLineString";
      coordinates: number[][][];
    };

export interface RoadFeature {
  type: "Feature";
  id?: string;
  geometry: RoadGeometry;
  properties: RoadFeatureProperties;
}

export interface RoadFeatureCollection {
  type: "FeatureCollection";
  features: RoadFeature[];
}

export interface RoadRiskItem {
  road_segment_id: string;
  road_name: string | null;
  road_class: string;
  length_m: number;
  status: RoadStatusType;
  safety_score: number;
  disruption_probability: number | null;
  score_confidence: number | null;
  score_type: string;
  model_name: string | null;
  model_version: string | null;
  reason_codes: string[];
  is_stale: boolean;
  is_unknown: boolean;
  score_updated_at: string | null;
  score_valid_until: string | null;
  coordinates?: number[][];
}

export interface RoadRiskListResponse {
  total: number;
  limit: number;
  offset: number;
  items: RoadRiskItem[];
}
