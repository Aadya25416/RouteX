"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";
import { getStatusColor, FALLBACK_CORRIDOR_BBOX } from "@/components/RoadMap";
import { api } from "@/lib/api";
import HomeFooter from "@/components/home/HomeFooter";

// Dynamically import MapLibre component with SSR disabled
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center w-full h-full bg-[#EAF2E7] text-[#193B32] gap-3">
      <div className="w-8 h-8 border-3 border-[#16A779] border-t-transparent rounded-full animate-spin" />
      <p className="text-sm font-semibold">Initializing MapLibre GL road network engine...</p>
    </div>
  ),
});

interface FetchedNetworkData {
  backendInfo: BackendInfoResponse;
  roadsData: RoadFeatureCollection;
}

async function fetchNetworkData(
  onStep?: (step: string) => void
): Promise<FetchedNetworkData> {
  // 1. Fetch backend info (corridor bounds & attribution)
  const infoData = await api.get<BackendInfoResponse>("/backend-api/info");

  // 2. Fetch real road geometry GeoJSON
  if (onStep) {
    onStep("Fetching canonical road geometry from GET /api/v1/roads/geojson ...");
  }
  const roadsGeoJson = await api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500");

  return { backendInfo: infoData, roadsData: roadsGeoJson };
}

export default function RoadNetworkPage() {
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [selectedRoad, setSelectedRoad] = useState<RoadFeatureProperties | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadingStep, setLoadingStep] = useState<string>("Fetching corridor bounds and attribution from GET / ...");
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setLoadingStep("Fetching corridor bounds and attribution from GET / ...");

    fetchNetworkData((step) => {
      setLoadingStep(step);
    })
      .then(({ backendInfo: info, roadsData: roads }) => {
        setBackendInfo(info);
        setRoadsData(roads);
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to connect to RouteX backend service at http://127.0.0.1:8000.";
        setError(message);
        setBackendInfo(null);
        setRoadsData(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    let ignore = false;

    fetchNetworkData((step) => {
      if (!ignore) {
        setLoadingStep(step);
      }
    })
      .then(({ backendInfo: info, roadsData: roads }) => {
        if (!ignore) {
          setBackendInfo(info);
          setRoadsData(roads);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          const message =
            err instanceof Error
              ? err.message
              : "Failed to connect to RouteX backend service at http://127.0.0.1:8000.";
          setError(message);
          setBackendInfo(null);
          setRoadsData(null);
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="flex flex-col min-h-screen w-full bg-[#FAFBF7] text-[#193B32]">
      {/* Top Header: RouteX Logistics Brand & Status */}
      <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between px-6 py-3.5 border-b border-[#DCE5D8] bg-white/95 backdrop-blur-md shadow-xs gap-3">
        <div className="flex items-center gap-3">
          <Link href="/home" className="flex items-center gap-1.5 text-decoration-none group" aria-label="RouteX Home">
            <span className="text-xl font-black tracking-tight text-[#193B32] group-hover:text-[#16A779] transition-colors">
              Route<span className="text-[#16A779]">X</span>
            </span>
            <span className="text-[10px] font-bold uppercase bg-[#DDF4E8] text-[#12432A] px-2 py-0.5 rounded tracking-wide border border-[#B7E4CD]">
              Logistics
            </span>
          </Link>
          <span className="text-[#DCE5D8] hidden sm:inline" aria-hidden="true">|</span>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#16A779] animate-pulse" aria-hidden="true" />
            <h1 className="text-sm font-bold text-[#193B32]">
              Guwahati–Tawang Road Network
            </h1>
          </div>
        </div>

        <div className="flex items-center flex-wrap gap-4 text-xs">
          <div className="hidden md:flex items-center gap-2 text-[#71877D]">
            <span>Corridor:</span>
            <span className="font-semibold text-[#193B32] bg-[#F1F4E8] px-2 py-0.5 rounded-full border border-[#DCE5D8]">
              {backendInfo?.corridor?.name || "Guwahati–Tawang"}
            </span>
          </div>

          <div className="flex items-center gap-2 text-[#71877D]">
            <span>Loaded:</span>
            <span className="font-semibold text-[#12432A] bg-[#DDF4E8] px-2 py-0.5 rounded-full border border-[#B7E4CD]">
              {roadsData ? `${roadsData.features.length} segments` : "Connecting..."}
            </span>
          </div>

          <nav className="flex items-center gap-2 font-semibold">
            <Link
              href="/home"
              className="px-3 py-1.5 rounded-full text-[#71877D] hover:text-[#193B32] hover:bg-[#F1F4E8] transition-colors"
            >
              Home
            </Link>
            <Link
              href="/driver"
              className="px-3 py-1.5 rounded-full text-[#71877D] hover:text-[#193B32] hover:bg-[#F1F4E8] transition-colors"
            >
              Driver
            </Link>
            <Link
              href="/admin"
              className="px-3 py-1.5 rounded-full bg-[#12432A] text-white hover:bg-[#0d3420] transition-colors"
            >
              Admin
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Map Canvas Area */}
      <main className="relative w-full h-[calc(100vh-140px)] min-h-[620px] flex-1 flex flex-col" style={{ minHeight: "620px", position: "relative" }}>
        {/* Map Component */}
        <RoadMap
          backendInfo={backendInfo}
          roadsData={roadsData}
          onSelectRoad={setSelectedRoad}
          className="w-full h-full min-h-[620px] flex-1 relative"
        />


        {/* Zero-Segments Empty Data Status Message (Requirement 8) */}
        {!isLoading && !error && roadsData && roadsData.features.length === 0 && (
          <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-10 max-w-lg w-full px-4 pointer-events-none">
            <div className="bg-white/95 backdrop-blur-md border border-[#DCE5D8] rounded-2xl shadow-xl p-3.5 text-center pointer-events-auto">
              <div className="flex items-center justify-center gap-2 text-xs font-bold text-[#193B32]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#16A779] animate-pulse" />
                <span>Corridor Basemap Active</span>
                <span className="text-[#8F9E97]">•</span>
                <span className="text-[#71877D] font-medium">0 segments loaded from database</span>
              </div>
              <p className="text-[11px] text-[#71877D] mt-1 leading-normal">
                The Guwahati–Tawang corridor basemap is fully active. Canonical road segments from the RouteX database will render automatically when available.
              </p>
            </div>
          </div>
        )}

        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-[#FAFBF7]/85 backdrop-blur-xs">
            <div className="flex flex-col items-center p-6 rounded-2xl bg-white border border-[#DCE5D8] shadow-2xl max-w-sm text-center">
              <div className="w-9 h-9 border-3 border-[#16A779] border-t-transparent rounded-full animate-spin mb-3" />
              <h2 className="text-sm font-bold text-[#193B32] mb-1">Loading Road Network</h2>
              <p className="text-xs text-[#71877D] animate-pulse">{loadingStep}</p>
            </div>
          </div>
        )}

        {/* Offline / Backend Error Overlay */}
        {error && !isLoading && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/35 backdrop-blur-xs p-4">
            <div className="p-6 rounded-2xl bg-white border border-[#FCE1B6] shadow-2xl max-w-md w-full">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl" aria-hidden="true">⚠️</span>
                <div>
                  <h2 className="text-sm font-bold text-[#193B32]">Backend Connection Offline</h2>
                  <p className="text-xs text-[#DC4848] font-medium">{error}</p>
                </div>
              </div>

              <p className="text-xs text-[#71877D] mb-4 leading-relaxed">
                The frontend is running, but the RouteX FastAPI service is not reachable at{" "}
                <code className="text-[#193B32] bg-[#F1F4E8] px-1 py-0.5 rounded font-mono">http://127.0.0.1:8000</code>.
                Per master PRD rules, <strong>no synthetic or mock roads</strong> will be fabricated.
              </p>

              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={loadData}
                  className="px-4 py-2 text-xs font-semibold rounded-full bg-[#16A779] hover:bg-[#128a63] text-white transition-colors cursor-pointer"
                >
                  Retry Connection
                </button>
                <span className="text-[11px] text-[#8F9E97]">
                  Run: <code className="text-[#193B32] font-mono">uv run uvicorn backend.main:app</code>
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Floating Road Status Legend */}
        <aside className="absolute top-4 left-4 z-10 w-76 bg-white/95 border border-[#DCE5D8] rounded-2xl shadow-xl backdrop-blur-md p-4 text-xs text-[#193B32]">
          <h2 className="font-bold text-[#193B32] mb-2.5 flex items-center justify-between text-xs">
            <span>Road Segment Status</span>
            <span className="text-[10px] font-bold text-[#12432A] bg-[#DDF4E8] px-1.5 py-0.5 rounded border border-[#B7E4CD] uppercase">
              Live Spec
            </span>
          </h2>

          <div className="space-y-2 mb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("OPEN") }} />
                <span className="text-[#193B32] font-semibold">OPEN</span>
              </div>
              <span className="text-[11px] text-[#71877D]">Passable corridor</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("AT_RISK") }} />
                <span className="text-[#193B32] font-semibold">AT_RISK</span>
              </div>
              <span className="text-[11px] text-[#71877D]">Weather / hazard caution</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("RESTRICTED") }} />
                <span className="text-[#193B32] font-semibold">RESTRICTED</span>
              </div>
              <span className="text-[11px] text-[#71877D]">Weight / access limits</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("BLOCKED") }} />
                <span className="text-[#193B32] font-semibold">BLOCKED</span>
              </div>
              <span className="text-[11px] text-[#71877D]">Hard road closure</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("UNKNOWN") }} />
                <span className="text-[#193B32] font-semibold">UNKNOWN</span>
              </div>
              <span className="text-[11px] text-[#71877D]">Unverified segment</span>
            </div>
          </div>

          <div className="pt-2.5 border-t border-[#E8EFE5] text-[11px] text-[#71877D] space-y-1">
            <p className="text-[#A66007] font-semibold">
              ⚠️ Policy: UNKNOWN is never treated as safe or open.
            </p>
            <p className="text-[#8F9E97]">
              Safety Score: 0–100 · Disruption Prob: 0.0–1.0
            </p>
          </div>
        </aside>

        {/* Selected Road Segment Inspector (if segment clicked) */}
        {selectedRoad && (
          <aside className="absolute top-4 right-14 z-10 w-84 bg-white/95 border border-[#DCE5D8] rounded-2xl shadow-xl backdrop-blur-md p-4 text-xs text-[#193B32]">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
              <h2 className="font-bold text-[#193B32] text-xs">Segment Inspector</h2>
              <button
                type="button"
                onClick={() => setSelectedRoad(null)}
                className="text-[#71877D] hover:text-[#193B32] text-sm font-bold cursor-pointer"
                aria-label="Close inspector"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2.5">
              <div>
                <span className="text-[#8F9E97] text-[11px] block">Road Segment Name</span>
                <p className="font-bold text-[#193B32]">{selectedRoad.name || "Unnamed Segment"}</p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Canonical ID</span>
                  <p className="font-mono text-[11px] text-[#71877D]">{selectedRoad.id}</p>
                </div>
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Current Status</span>
                  <p className="font-bold" style={{ color: getStatusColor(selectedRoad.status) }}>
                    {selectedRoad.status}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Road Class</span>
                  <p className="capitalize text-[#193B32] font-medium">{selectedRoad.road_class || "N/A"}</p>
                </div>
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Length</span>
                  <p className="text-[#193B32] font-medium">
                    {selectedRoad.length_m ? `${(selectedRoad.length_m / 1000).toFixed(2)} km` : "N/A"}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#E8EFE5]">
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Safety Score</span>
                  <p className="font-bold text-[#193B32]">
                    {selectedRoad.safety_score != null ? `${selectedRoad.safety_score.toFixed(1)} / 100` : "N/A"}
                  </p>
                </div>
                <div>
                  <span className="text-[#8F9E97] text-[11px] block">Disruption Risk</span>
                  <p className="font-bold text-[#193B32]">
                    {selectedRoad.disruption_probability != null
                      ? `${(selectedRoad.disruption_probability * 100).toFixed(1)}%`
                      : "Not evaluated"}
                  </p>
                </div>
              </div>

              {selectedRoad.status === "UNKNOWN" && (
                <div className="mt-2 p-2 rounded-lg bg-[#FFF8EB] border border-[#FCE1B6] text-[#A66007] text-[11px]">
                  ⚠️ <strong>Unverified segment:</strong> Safety assessment pending field officer confirmation.
                </div>
              )}
            </div>
          </aside>
        )}
      </main>

      {/* Standardized Multi-Column RouteX Global Footer */}
      <HomeFooter />
    </div>
  );
}
