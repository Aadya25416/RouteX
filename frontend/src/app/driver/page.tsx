"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import DriverLayout from "@/components/driver/DriverLayout";
import RouteStops from "@/components/driver/RouteStops";
import QuickIncidentReporting from "@/components/driver/QuickIncidentReporting";
import { INITIAL_DRIVER_TRIP, GUWAHATI_TAWANG_CORRIDOR_COORDS } from "@/data/driverData";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

// Dynamically import RoadMap to avoid SSR MapLibre errors
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[240px] bg-[#EAF2E7] rounded-xl flex items-center justify-center text-xs text-[#71877D]">
      Initializing MapLibre preview...
    </div>
  ),
});

import { api } from "@/lib/api";
import { useGpsTracker } from "@/lib/useGpsTracker";
import { connectEventStream } from "@/lib/events";
import type { VehicleMarkerData } from "@/components/RoadMap";

interface BackendTripItem {
  id: string;
  status: string;
  vehicle_id?: string;
  estimated_duration_s?: number;
  estimated_distance_m?: number;
  vehicle?: { id: string; registration_number?: string; vehicle_code?: string };
  delivery?: {
    id: string;
    origin_name?: string;
    destination_name?: string;
  };
}

interface TripListResponse {
  total: number;
  items: BackendTripItem[];
}

export default function DriverDashboardPage() {
  const [trip, setTrip] = useState(INITIAL_DRIVER_TRIP);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [activeBackendTrip, setActiveBackendTrip] = useState<BackendTripItem | null>(null);
  const [driverMarker, setDriverMarker] = useState<VehicleMarkerData | null>(null);
  const [rerouteNotice, setRerouteNotice] = useState<{
    message: string;
    timestamp: string;
    newDistanceM?: number;
    newDurationS?: number;
  } | null>(null);

  // Hook into browser geolocation tracking with 5s cadence
  const vehicleId = activeBackendTrip?.vehicle?.id || activeBackendTrip?.vehicle_id;

  const handleFixSent = useCallback((fix: { longitude: number; latitude: number; speedKmh: number | null; headingDeg: number | null; timestamp: string }) => {
    if (vehicleId) {
      setDriverMarker({
        id: vehicleId,
        lngLat: [fix.longitude, fix.latitude],
        label: trip.vehicleNumber || "My Vehicle",
        speedKmh: fix.speedKmh,
        heading: fix.headingDeg,
        isCurrentDriver: true,
        isStale: false,
        updatedAt: fix.timestamp,
      });
    }
  }, [vehicleId, trip.vehicleNumber]);

  const {
    isTracking,
    startTracking,
    stopTracking,
    lastFix,
    trackingError,
    lastSyncedAt,
  } = useGpsTracker({
    minIntervalMs: 5000,
    onFixSent: handleFixSent,
  });

  // Connect to SSE stream for backend-confirmed telemetry & trip reroute events
  useEffect(() => {
    const unsubscribe = connectEventStream({
      onEvent: (event) => {
        if (event.event_type === "vehicle.location_updated") {
          const payload = event.payload;
          if (payload.vehicle_id === vehicleId) {
            setDriverMarker({
              id: payload.vehicle_id,
              lngLat: [payload.longitude, payload.latitude],
              label: trip.vehicleNumber || "My Vehicle",
              speedKmh: payload.speed_kmh,
              heading: payload.heading_deg,
              isCurrentDriver: true,
              isStale: false,
              updatedAt: payload.recorded_at,
            });
          }
        } else if (event.event_type === "trip.rerouted") {
          if (event.payload.trip_id === activeBackendTrip?.id) {
            setRerouteNotice({
              message: event.payload.reason || "Trip rerouted to avoid road hazards",
              timestamp: event.timestamp,
              newDistanceM: event.payload.estimated_distance_m,
              newDurationS: event.payload.estimated_duration_s,
            });
            if (event.payload.estimated_distance_m) {
              setTrip((prev) => ({
                ...prev,
                totalDistanceKm: Math.round(event.payload.estimated_distance_m / 1000),
                estimatedDuration: event.payload.estimated_duration_s
                  ? `${Math.round(event.payload.estimated_duration_s / 60)} min`
                  : prev.estimatedDuration,
              }));
            }
          }
        } else if (event.event_type === "road.status_changed") {
          api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
            .then((data) => setRoadsData(data))
            .catch(() => {});
        }
      },
    });

    return () => {
      unsubscribe();
    };
  }, [vehicleId, activeBackendTrip?.id, trip.vehicleNumber]);

  useEffect(() => {
    let isMounted = true;

    api.get<BackendInfoResponse>("/backend-api/info")
      .then((data) => {
        if (isMounted) setBackendInfo(data);
      })
      .catch(() => {});

    api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
      .then((data) => {
        if (isMounted) setRoadsData(data);
      })
      .catch(() => {});

    // Fetch driver's real assigned trips
    api
      .get<TripListResponse>("/api/v1/trips?limit=10")
      .then((data) => {
        if (isMounted && data && data.items && data.items.length > 0) {
          const active = data.items.find((t) => t.status === "IN_TRANSIT" || t.status === "PLANNED") || data.items[0];
          if (active) {
            setActiveBackendTrip(active);
            const vehNumber = active.vehicle?.registration_number || active.vehicle?.vehicle_code;
            setTrip((prev) => ({
              ...prev,
              id: active.id,
              vehicleNumber: vehNumber || prev.vehicleNumber,
              origin: active.delivery?.origin_name || prev.origin,
              destination: active.delivery?.destination_name || prev.destination,
              totalDistanceKm: active.estimated_distance_m ? Math.round(active.estimated_distance_m / 1000) : prev.totalDistanceKm,
              estimatedDuration: active.estimated_duration_s ? `${Math.round(active.estimated_duration_s / 60)} min` : prev.estimatedDuration,
            }));

            // Fetch initial latest location from Redis cache
            const vId = active.vehicle?.id || active.vehicle_id;
            if (vId) {
              api.get<{ latitude: number; longitude: number; speed_kmh?: number; recorded_at: string }>(`/api/v1/vehicles/${vId}/location`)
                .then((loc) => {
                  if (isMounted && loc) {
                    setDriverMarker({
                      id: vId,
                      lngLat: [loc.longitude, loc.latitude],
                      label: vehNumber || "My Vehicle",
                      speedKmh: loc.speed_kmh,
                      isCurrentDriver: true,
                      isStale: false,
                      updatedAt: loc.recorded_at,
                    });
                  }
                })
                .catch(() => {});
            }
          }
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  const stopMarkers = trip.stops.map((s) => ({
    lngLat: s.coordinates,
    label: s.name,
    isDestination: s.isDestination,
    isNext: s.isNext,
  }));

  const hazardMarker = trip.hazardDetails
    ? {
        lngLat: trip.hazardDetails.coordinates,
        label: "Landslide Risk",
        type: trip.hazardDetails.type,
      }
    : null;

  return (
    <DriverLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        {/* Top Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-[#193B32]">My Route</h1>
            <div className="relative">
              <select
                aria-label="Trip date filter"
                defaultValue="today"
                className="appearance-none bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 pl-3 pr-7 rounded-full cursor-pointer focus:outline-none focus:border-[#16A779] shadow-xs"
              >
                <option value="today">Today</option>
                <option value="tomorrow">Tomorrow</option>
                <option value="all">All Trips</option>
              </select>
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-[#71877D] text-[10px]">
                ▼
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Start / Stop GPS Tracking Button */}
            <button
              type="button"
              onClick={() => {
                if (isTracking) {
                  stopTracking();
                } else if (vehicleId) {
                  startTracking(vehicleId, activeBackendTrip?.id);
                }
              }}
              id="driver-toggle-tracking-btn"
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-2 cursor-pointer ${
                isTracking
                  ? "bg-rose-600 hover:bg-rose-700 text-white"
                  : "bg-[#16A779] hover:bg-[#128a63] text-white"
              }`}
            >
              <span className={`w-2.5 h-2.5 rounded-full ${isTracking ? "bg-white animate-pulse" : "bg-emerald-200"}`} />
              <span>{isTracking ? "Stop GPS Tracking" : "Start Tracking"}</span>
            </button>

            <Link href="/driver/navigation" className="rx-btn-primary" id="start-nav-btn">
              <span>Start Navigation</span>
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        {/* Live GPS Telemetry Status Bar */}
        <div className="flex flex-wrap items-center justify-between px-4 py-2.5 bg-white border border-[#DCE5D8] rounded-xl text-xs shadow-xs">
          <div className="flex items-center gap-2.5">
            <span className={`w-2.5 h-2.5 rounded-full ${isTracking ? "bg-[#16A779] animate-ping" : "bg-slate-400"}`} />
            <span className="font-bold text-[#193B32]">
              {isTracking ? "GPS Tracking Active (5s Auto-Sync)" : "GPS Telemetry Paused"}
            </span>
            {lastSyncedAt && (
              <span className="text-[#71877D] ml-1">
                · Last Synced: <strong>{new Date(lastSyncedAt).toLocaleTimeString()}</strong>
              </span>
            )}
            {lastFix?.accuracy && (
              <span className="text-[#71877D] ml-1 font-mono text-[11px]">
                (±{Math.round(lastFix.accuracy)}m)
              </span>
            )}
          </div>
          {trackingError && (
            <span className="text-rose-600 font-bold flex items-center gap-1.5">
              <span>⚠️</span>
              <span>{trackingError}</span>
            </span>
          )}
        </div>

        {/* Real-time Reroute Notification Banner */}
        {rerouteNotice && (
          <div className="bg-[#FFF8EB] border-l-4 border-[#F4B64A] p-4 rounded-xl shadow-xs flex items-center justify-between text-[#854D0E] animate-fadeIn">
            <div className="flex items-center gap-3">
              <span className="text-xl">⚠️</span>
              <div>
                <p className="font-bold text-sm">Corridor Reroute Notification</p>
                <p className="text-xs text-[#A16207]">{rerouteNotice.message}</p>
              </div>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 bg-[#FEF3C7] rounded-lg">
              Updated {new Date(rerouteNotice.timestamp).toLocaleTimeString()}
            </span>
          </div>
        )}

        {/* Central Trip Card: Left Timeline & Right Map */}
        <div className="rx-card bg-white border border-[#E5E7EB] grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
          {/* Left Column: Route Stops Timeline */}
          <div className="lg:col-span-6 flex flex-col justify-between">
            <RouteStops stops={trip.stops} />

            <div className="pt-6 mt-4 border-t border-[#E8EFE5] flex items-center justify-between text-xs text-[#71877D]">
              <span>Assigned Vehicle: <strong className="text-[#193B32]">{trip.vehicleNumber}</strong></span>
              <span className="font-mono text-[11px]">{trip.id}</span>
            </div>
          </div>

          {/* Right Column: Route Map Preview */}
          <div className="lg:col-span-6 relative rounded-2xl overflow-hidden border border-[#DCE5D8] min-h-[300px] h-[340px] bg-[#EAF2E7]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              routeCoordinates={GUWAHATI_TAWANG_CORRIDOR_COORDS}
              stopMarkers={stopMarkers}
              hazardMarker={hazardMarker}
              vehicleMarkers={driverMarker ? [driverMarker] : []}
              customCenter={driverMarker ? driverMarker.lngLat : [92.1, 26.9]}
              customZoom={driverMarker ? 8.5 : 7.3}
              hideNavControls={true}
              className="w-full h-full relative"
            />

            {/* Recenter / Locate Button Overlay */}
            <Link
              href="/driver/navigation"
              title="Open full interactive navigation map"
              className="absolute bottom-3 right-3 z-10 w-9 h-9 bg-white rounded-xl shadow-md border border-[#DCE5D8] flex items-center justify-center text-[#193B32] hover:bg-[#F9FAF6] transition-colors"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polygon points="3 11 22 2 13 21 11 13 3 11" />
              </svg>
            </Link>
          </div>
        </div>

        {/* Report a Road Incident Section */}
        <QuickIncidentReporting />
      </div>
    </DriverLayout>
  );
}
