/**
 * TypeScript types strictly mirroring the RouteX / NER-LINK FastAPI schemas.
 * References: backend/schemas/roads.py and backend/main.py root handler.
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
