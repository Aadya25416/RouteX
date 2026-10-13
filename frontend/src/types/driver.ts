/**
 * RouteX / NER-LINK — Driver Experience Types
 * Defined to match the 4-screen Driver Dashboard workflow and API contracts.
 */

export type DriverIncidentType = "landslide" | "road_block" | "weather" | "other";

export type StopStatus = "Departed" | "Completed" | "Next stop" | "Destination" | "Reached" | "Delivered";

export interface TripStop {
  id: string;
  name: string;
  time: string;
  status: StopStatus;
  isCompleted?: boolean;
  isNext?: boolean;
  isDestination?: boolean;
  coordinates: [number, number]; // [lng, lat]
}

export interface DriverTrip {
  id: string;
  origin: string;
  destination: string;
  corridor: string; // e.g. "NH-27"
  totalDistanceKm: number; // e.g. 520
  estimatedDuration: string; // e.g. "12 hr 30 min"
  actualDuration?: string; // e.g. "12 hr 45 min"
  vehicleNumber: string; // e.g. "Truck (MH 12 AB 1234)"
  vehicleType: string;
  status: "PLANNED" | "IN_TRANSIT" | "PAUSED" | "COMPLETED";
  stops: TripStop[];
  hasHazardWarning?: boolean;
  hazardDetails?: {
    location: string;
    type: DriverIncidentType;
    severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
    message: string;
    coordinates: [number, number];
  };
}

export interface IncidentFormState {
  incidentType: DriverIncidentType;
  description: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
  photos: File[];
  isSubmitting: boolean;
  submittedId: string | null;
  error: string | null;
}
