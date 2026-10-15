"use client";

import React, { useState, useEffect } from "react";
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

interface BackendTripItem {
  id: string;
  status: string;
  estimated_duration_s?: number;
  estimated_distance_m?: number;
  vehicle?: { id: string; registration_number?: string };
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
            setTrip((prev) => ({
              ...prev,
              id: active.id,
              origin: active.delivery?.origin_name || prev.origin,
              destination: active.delivery?.destination_name || prev.destination,
              totalDistanceKm: active.estimated_distance_m ? Math.round(active.estimated_distance_m / 1000) : prev.totalDistanceKm,
              estimatedDuration: active.estimated_duration_s ? `${Math.round(active.estimated_duration_s / 60)} min` : prev.estimatedDuration,
            }));
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

          <Link href="/driver/navigation" className="rx-btn-primary" id="start-nav-btn">
            <span>Start Navigation</span>
            <span aria-hidden="true">→</span>
          </Link>
        </div>

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
              customCenter={[92.1, 26.9]}
              customZoom={7.3}
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
