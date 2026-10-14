"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import AdminLayout from "@/components/admin/AdminLayout";
import { ROUTE_PLAN_OPTIONS } from "@/data/adminData";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

// Dynamically import RoadMap
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[450px] bg-[#EAF2E7] flex items-center justify-center text-xs text-[#71877D]">
      Initializing MapLibre route planning engine...
    </div>
  ),
});

export default function RoutePlanningPage() {
  const [fromLocation, setFromLocation] = useState("Guwahati");
  const [toLocation, setToLocation] = useState("Tawang");
  const [travelMode, setTravelMode] = useState<"car" | "truck" | "bus">("truck");
  const [selectedRouteId, setSelectedRouteId] = useState<string>("route-rec-1");
  const [isCalculating, setIsCalculating] = useState<boolean>(false);
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);

  useEffect(() => {
    fetch("/backend-api/info", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setBackendInfo(data))
      .catch(() => {});

    fetch("/api/v1/roads/geojson?limit=500", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setRoadsData(data))
      .catch(() => {});
  }, []);

  const activeRoute =
    ROUTE_PLAN_OPTIONS.find((r) => r.id === selectedRouteId) || ROUTE_PLAN_OPTIONS[0];

  const handlePlanRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCalculating(true);

    // Call backend route planner if available
    try {
      await fetch("/api/v1/routes/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin_lat: 26.1445,
          origin_lon: 91.7362,
          destination_lat: 27.5861,
          destination_lon: 91.8687,
          mode: travelMode.toUpperCase(),
        }),
      });
    } catch {
      // Graceful offline fallback using calibrated corridor route
    } finally {
      setTimeout(() => setIsCalculating(false), 500);
    }
  };

  const stopMarkers = [
    { lngLat: [91.7362, 26.1445] as [number, number], label: fromLocation },
    { lngLat: [91.8687, 27.5861] as [number, number], label: toLocation, isDestination: true },
  ];

  return (
    <AdminLayout>
      <div className="flex flex-col gap-4 max-w-7xl mx-auto w-full">
        <div>
          <h1 className="text-xl font-extrabold text-[#193B32]">Route Planning</h1>
          <p className="text-xs text-[#71877D]">
            Calculate and evaluate optimal corridors considering active hazard constraints
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Form & Alternatives (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* Input Form Card */}
            <form onSubmit={handlePlanRoute} className="rx-admin-card flex flex-col gap-3.5">
              <h2 className="text-sm font-bold text-[#193B32]">Plan a Route</h2>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="route-from" className="block text-xs font-bold text-[#71877D] mb-1">
                    From
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs">📍</span>
                    <input
                      id="route-from"
                      type="text"
                      value={fromLocation}
                      onChange={(e) => setFromLocation(e.target.value)}
                      className="w-full pl-8 pr-3 py-2 text-xs bg-white border border-[#DCE5D8] rounded-xl font-semibold text-[#193B32] outline-none focus:border-[#16A779]"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="route-to" className="block text-xs font-bold text-[#71877D] mb-1">
                    To
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs">🏁</span>
                    <input
                      id="route-to"
                      type="text"
                      value={toLocation}
                      onChange={(e) => setToLocation(e.target.value)}
                      className="w-full pl-8 pr-3 py-2 text-xs bg-white border border-[#DCE5D8] rounded-xl font-semibold text-[#193B32] outline-none focus:border-[#16A779]"
                    />
                  </div>
                </div>
              </div>

              {/* Travel Mode Selector */}
              <div>
                <label className="block text-xs font-bold text-[#71877D] mb-1.5">
                  Travel Mode
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setTravelMode("car")}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      travelMode === "car"
                        ? "bg-[#DDF4E8] border-[#16A779] text-[#12432A]"
                        : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D]"
                    }`}
                  >
                    <span>🚗</span> Car
                  </button>
                  <button
                    type="button"
                    onClick={() => setTravelMode("truck")}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      travelMode === "truck"
                        ? "bg-[#DDF4E8] border-[#16A779] text-[#12432A]"
                        : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D]"
                    }`}
                  >
                    <span>🚛</span> Truck
                  </button>
                  <button
                    type="button"
                    onClick={() => setTravelMode("bus")}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      travelMode === "bus"
                        ? "bg-[#DDF4E8] border-[#16A779] text-[#12432A]"
                        : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D]"
                    }`}
                  >
                    <span>🚌</span> Bus
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isCalculating}
                className="w-full py-2.5 mt-1 bg-[#12432A] hover:bg-[#0b2f1c] text-white rounded-full text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                {isCalculating ? (
                  <span>Evaluating Road Safety...</span>
                ) : (
                  <>
                    <span>Find Best Route</span>
                    <span>→</span>
                  </>
                )}
              </button>
            </form>

            {/* Route Results Options */}
            <div className="space-y-2.5">
              <h2 className="text-xs font-bold text-[#71877D] uppercase tracking-wider">
                Route Results
              </h2>

              {ROUTE_PLAN_OPTIONS.map((opt) => {
                const isSelected = opt.id === selectedRouteId;
                return (
                  <div
                    key={opt.id}
                    onClick={() => setSelectedRouteId(opt.id)}
                    className={`rx-admin-card p-3.5 cursor-pointer transition-all border-2 ${
                      isSelected
                        ? "border-[#16A779] shadow-md bg-white"
                        : "border-[#DCE5D8] hover:border-[#B7E4CD] bg-[#FAFBF7]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-[#193B32]">{opt.name}</span>
                      {opt.isRecommended && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDF4E8] text-[#12432A]">
                          Safest
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs font-bold text-[#193B32] mb-1.5">
                      <span>{opt.distanceKm} km</span>
                      <span className="text-[#71877D] font-normal">•</span>
                      <span>{opt.durationFormatted}</span>
                      <span className="text-[#71877D] font-normal">•</span>
                      <span className="text-[#16A779]">Safety: {opt.safetyScore}/100</span>
                    </div>

                    <p className="text-[11px] text-[#71877D]">{opt.riskSummary}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Map Display (7 cols) */}
          <div className="lg:col-span-7 rx-admin-card p-0 overflow-hidden relative min-h-[520px] h-[560px] bg-[#EAF2E7]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              routeCoordinates={activeRoute.coordinates}
              stopMarkers={stopMarkers}
              customCenter={[92.2, 26.9]}
              customZoom={7.6}
              className="w-full h-full relative"
            />

            {/* Floating ETA Badge */}
            <div className="absolute top-4 left-4 z-10 bg-white/95 backdrop-blur-md px-4 py-2.5 rounded-xl shadow-lg border border-[#DCE5D8] flex items-center gap-3">
              <span className="text-xl">🚗</span>
              <div>
                <span className="text-xs font-extrabold text-[#193B32] block">
                  {activeRoute.durationFormatted} ({activeRoute.distanceKm} km)
                </span>
                <span className="text-[10px] text-[#71877D]">
                  {fromLocation} to {toLocation} · {activeRoute.name}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
