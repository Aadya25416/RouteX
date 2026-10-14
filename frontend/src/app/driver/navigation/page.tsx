"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import DriverLayout from "@/components/driver/DriverLayout";
import { INITIAL_DRIVER_TRIP, GUWAHATI_TAWANG_CORRIDOR_COORDS } from "@/data/driverData";
import { getStatusColor } from "@/components/RoadMap";
import { api, ApiError } from "@/lib/api";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";

interface BackendTripItem {
  id: string;
  vehicle_id: string;
  delivery_id: string;
  driver_id: string;
  status: string;
  estimated_duration_s?: number;
  estimated_distance_m?: number;
  vehicle?: {
    id: string;
    registration_number: string;
    vehicle_code: string;
  };
  delivery?: {
    id: string;
    pickup_address?: string;
    dropoff_address?: string;
  };
}

interface TripListResponse {
  total: number;
  items: BackendTripItem[];
}

// Dynamically import RoadMap
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center w-full h-full bg-[#EAF2E7] text-[#193B32] gap-3">
      <div className="w-8 h-8 border-3 border-[#16A779] border-t-transparent rounded-full animate-spin" />
      <p className="text-xs font-semibold">Loading MapLibre navigation engine...</p>
    </div>
  ),
});

export default function ActiveNavigationPage() {
  const router = useRouter();
  const [trip] = useState(INITIAL_DRIVER_TRIP);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [selectedRoad, setSelectedRoad] = useState<RoadFeatureProperties | null>(null);
  const [activeBackendTrip, setActiveBackendTrip] = useState<BackendTripItem | null>(null);
  const [isCompleting, setIsCompleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [telemetryStatus, setTelemetryStatus] = useState<string | null>(null);

  useEffect(() => {
    api.get<BackendInfoResponse>("/backend-api/info")
      .then(setBackendInfo)
      .catch(() => {});

    api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
      .then(setRoadsData)
      .catch(() => {});

    api.get<TripListResponse>("/api/v1/trips?limit=10")
      .then((res) => {
        const inTransit = res.items.find((t) => t.status === "IN_TRANSIT" || t.status === "PLANNED");
        if (inTransit) setActiveBackendTrip(inTransit);
      })
      .catch(() => {});
  }, []);

  const handleCompleteTrip = async () => {
    if (!activeBackendTrip) {
      router.push("/driver/trip-complete");
      return;
    }
    setIsCompleting(true);
    setActionError(null);
    try {
      await api.post(`/api/v1/trips/${activeBackendTrip.id}/complete`);
      router.push("/driver/trip-complete");
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError("Failed to complete trip. Please check connection.");
      }
      setIsCompleting(false);
    }
  };

  const handleSendLocation = async () => {
    if (!activeBackendTrip?.vehicle_id) return;
    setTelemetryStatus("Sending GPS ping...");
    try {
      await api.post(`/api/v1/vehicles/${activeBackendTrip.vehicle_id}/location`, {
        latitude: 26.9,
        longitude: 92.2,
        recorded_at: new Date().toISOString(),
        speed_kmh: 42.5,
        heading_deg: 35.0,
        source: "mobile_gps",
        trip_id: activeBackendTrip.id,
      });
      setTelemetryStatus("GPS position synced");
      setTimeout(() => setTelemetryStatus(null), 3000);
    } catch (err) {
      setTelemetryStatus(err instanceof ApiError ? err.message : "GPS ping failed");
    }
  };

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
      <div className="flex flex-col h-[calc(100vh-80px)] w-full">
        {/* Subheader with Active Status */}
        <div className="flex items-center justify-between pb-3 px-1">
          <div>
            <h1 className="text-lg font-extrabold text-[#193B32]">Active Navigation</h1>
            <p className="text-xs text-[#71877D]">
              Guwahati–Tawang Corridor · Live operational guidance
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#DDF4E8] text-[#12432A] text-xs font-bold">
              <span className="w-2 h-2 rounded-full bg-[#16A779] animate-pulse" />
              In Transit
            </span>
          </div>
        </div>

        {/* Main Content: Map (Left/Center) + Route Details Panel (Right) */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-0 overflow-hidden">
          {/* Map Container */}
          <div className="lg:col-span-8 xl:col-span-9 relative rx-card p-0 overflow-hidden h-full min-h-[450px]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              routeCoordinates={GUWAHATI_TAWANG_CORRIDOR_COORDS}
              stopMarkers={stopMarkers}
              hazardMarker={hazardMarker}
              onSelectRoad={setSelectedRoad}
              customCenter={[92.2, 26.9]}
              customZoom={8.2}
              className="w-full h-full relative"
            />

            {/* Floating Navigation ETA Pill Overlay */}
            <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
              <div className="bg-white/95 backdrop-blur-md px-3.5 py-2 rounded-xl shadow-lg border border-[#DCE5D8] flex items-center gap-2.5">
                <span className="text-base">🚗</span>
                <div>
                  <span className="text-xs font-bold text-[#193B32] block leading-tight">25 min</span>
                  <span className="text-[10px] text-[#71877D]">NH-27 towards Nagaon</span>
                </div>
              </div>

              <div className="bg-white/95 backdrop-blur-md px-3.5 py-2 rounded-xl shadow-lg border border-[#DCE5D8] flex items-center gap-2.5">
                <span className="text-base">📍</span>
                <div>
                  <span className="text-xs font-bold text-[#193B32] block leading-tight">Next Stop: Bomdila</span>
                  <span className="text-[10px] text-[#71877D]">ETA 01:15 PM</span>
                </div>
              </div>
            </div>

            {/* Selected Segment Info popup if clicked */}
            {selectedRoad && (
              <div className="absolute bottom-4 left-4 z-20 max-w-xs bg-white/95 backdrop-blur-md p-3.5 rounded-xl border border-[#DCE5D8] shadow-xl text-xs">
                <div className="flex items-center justify-between mb-1 pb-1 border-b border-[#E8EFE5]">
                  <strong className="text-[#193B32]">{selectedRoad.name || "Road Segment"}</strong>
                  <button
                    type="button"
                    onClick={() => setSelectedRoad(null)}
                    className="text-gray-400 hover:text-black font-bold"
                  >
                    ✕
                  </button>
                </div>
                <div className="text-[11px] text-[#71877D] space-y-1">
                  <div>Status: <span className="font-bold" style={{ color: getStatusColor(selectedRoad.status) }}>{selectedRoad.status}</span></div>
                  <div>Safety Score: <strong>{selectedRoad.safety_score != null ? `${selectedRoad.safety_score}/100` : "N/A"}</strong></div>
                  <div>Length: {(selectedRoad.length_m / 1000).toFixed(2)} km</div>
                </div>
              </div>
            )}
          </div>

          {/* Right Route Details Panel */}
          <div className="lg:col-span-4 xl:col-span-3 rx-card flex flex-col justify-between overflow-y-auto">
            <div className="space-y-4">
              <div>
                <h2 className="text-xs font-bold text-[#71877D] uppercase tracking-wider mb-1">
                  Route Details
                </h2>
                <h3 className="text-base font-extrabold text-[#193B32]">
                  {trip.origin} → {trip.destination}
                </h3>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#FAFBF7] border border-[#DCE5D8] rounded-xl p-3">
                  <div className="flex items-center gap-1.5 text-xs text-[#71877D] mb-1">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="6" cy="19" r="3" />
                      <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
                      <circle cx="18" cy="5" r="3" />
                    </svg>
                    <span>Total Distance</span>
                  </div>
                  <span className="text-base font-bold text-[#193B32]">{trip.totalDistanceKm} km</span>
                </div>

                <div className="bg-[#FAFBF7] border border-[#DCE5D8] rounded-xl p-3">
                  <div className="flex items-center gap-1.5 text-xs text-[#71877D] mb-1">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span>Estimated Time</span>
                  </div>
                  <span className="text-base font-bold text-[#193B32]">{trip.estimatedDuration}</span>
                </div>
              </div>

              {/* Current Status Box */}
              <div className="p-3.5 rounded-xl bg-[#FFF8EB] border border-[#FCE1B6] text-xs">
                <div className="flex items-center gap-2 font-bold text-[#A66007] mb-1">
                  <span>⚠️</span>
                  <span>Current Status</span>
                </div>
                <p className="text-[11.5px] text-[#8C5305] leading-relaxed">
                  Landslide risk reported near Bomdila (Illustrative). Maintain reduced speed through sector 4.
                </p>
              </div>

              {/* Road Status Legend */}
              <div className="pt-2 border-t border-[#E8EFE5]">
                <h4 className="text-xs font-bold text-[#71877D] uppercase tracking-wider mb-2.5">
                  Road Segment Status
                </h4>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#16A779]" />
                      <span className="text-[#193B32] font-semibold">Open</span>
                    </div>
                    <span className="text-[11px] text-[#71877D]">Normal</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F4B64A]" />
                      <span className="text-[#193B32] font-semibold">At Risk</span>
                    </div>
                    <span className="text-[11px] text-[#71877D]">Caution</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F07838]" />
                      <span className="text-[#193B32] font-semibold">Restricted</span>
                    </div>
                    <span className="text-[11px] text-[#71877D]">Limits</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#DC4848]" />
                      <span className="text-[#193B32] font-semibold">Blocked</span>
                    </div>
                    <span className="text-[11px] text-[#71877D]">Closed</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#89939A]" />
                      <span className="text-[#193B32] font-semibold">Unknown</span>
                    </div>
                    <span className="text-[11px] text-[#71877D]">Unverified</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Action buttons at bottom of panel */}
            <div className="pt-4 mt-4 border-t border-[#E8EFE5] flex flex-col gap-2">
              {activeBackendTrip?.vehicle_id && (
                <button
                  type="button"
                  onClick={handleSendLocation}
                  className="w-full py-2 px-3 bg-[#EAF2E7] hover:bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD] rounded-full text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                >
                  <span>📡</span>
                  <span>{telemetryStatus || "Send GPS Ping"}</span>
                </button>
              )}
              <Link
                href="/driver/report-incident"
                className="w-full py-2.5 px-4 bg-[#FFF8EB] hover:bg-[#FCE1B6] text-[#A66007] border border-[#FCE1B6] rounded-full text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>⚠️</span>
                <span>Report Road Hazard</span>
              </Link>
              <button
                type="button"
                disabled={isCompleting}
                onClick={handleCompleteTrip}
                className="w-full py-2.5 px-4 bg-[#12432A] hover:bg-[#0d3420] text-white rounded-full text-xs font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {isCompleting ? (
                  <span>Completing Trip...</span>
                ) : (
                  <>
                    <span>Complete Trip</span>
                    <span>→</span>
                  </>
                )}
              </button>
              {actionError && (
                <p className="text-red-600 text-xs text-center mt-1 font-semibold">{actionError}</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </DriverLayout>
  );
}
