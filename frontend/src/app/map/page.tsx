"use client";

import React, { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";
import { getStatusColor } from "@/components/RoadMap";
import { api } from "@/lib/api";

// Dynamically import MapLibre component with SSR disabled
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center w-full h-full bg-zinc-900 text-zinc-300 gap-3">
      <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm font-medium">Initializing MapLibre GL engine...</p>
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
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 font-sans">
      {/* Top Header: Phase 1 Read-Only Status & Corridor Info */}
      <header className="flex flex-wrap items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-900/90 backdrop-blur z-20 gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-base font-bold tracking-tight text-white">RouteX</h1>
          </div>
          <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-medium">
            Phase 1: Read-Only Road Map
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-zinc-400">
          <div>
            <span className="text-zinc-500">Corridor:</span>{" "}
            <span className="font-semibold text-zinc-200">
              {backendInfo?.corridor?.name || "Guwahati-Tawang (Configured)"}
            </span>
          </div>
          <div>
            <span className="text-zinc-500">Loaded Segments:</span>{" "}
            <span className="font-semibold text-zinc-200">
              {roadsData ? `${roadsData.features.length} segments` : "0 (offline)"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Map View Area */}
      <main className="relative flex-1 w-full h-full overflow-hidden">
        {/* Map Component */}
        <RoadMap
          backendInfo={backendInfo}
          roadsData={roadsData}
          onSelectRoad={setSelectedRoad}
        />

        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-zinc-950/75 backdrop-blur-sm">
            <div className="flex flex-col items-center p-6 rounded-xl bg-zinc-900 border border-zinc-800 shadow-2xl max-w-sm text-center">
              <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
              <h2 className="text-sm font-semibold text-white mb-1">Loading Road Network</h2>
              <p className="text-xs text-zinc-400">{loadingStep}</p>
            </div>
          </div>
        )}

        {/* Honest Error Overlay: Backend Unavailable */}
        {error && !isLoading && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm p-4">
            <div className="max-w-md w-full bg-zinc-900 border border-red-500/40 rounded-xl p-6 shadow-2xl">
              <div className="flex items-center gap-3 mb-3">
                <span className="p-2 rounded-lg bg-red-500/10 text-red-400 text-lg">⚠️</span>
                <div>
                  <h2 className="text-base font-bold text-red-200">Backend Unavailable</h2>
                  <p className="text-xs text-red-400">Unable to fetch canonical road network</p>
                </div>
              </div>

              <div className="p-3 mb-4 rounded bg-zinc-950/70 border border-zinc-800 text-xs font-mono text-zinc-300 break-words">
                {error}
              </div>

              <p className="text-xs text-zinc-400 mb-5 leading-relaxed">
                The frontend is running, but the RouteX FastAPI service is not reachable at{" "}
                <code className="text-zinc-300 bg-zinc-800 px-1 py-0.5 rounded">http://127.0.0.1:8000</code>.
                Per master PRD rules, <strong>no synthetic or mock roads</strong> will be fabricated.
              </p>

              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={loadData}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
                >
                  Retry Connection
                </button>
                <span className="text-[11px] text-zinc-500">
                  Run: <code className="text-zinc-400">uvicorn backend.main:app --port 8000</code>
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Floating Road Status Legend */}
        <aside className="absolute top-4 left-4 z-10 w-72 bg-zinc-900/95 border border-zinc-800 rounded-lg shadow-xl backdrop-blur p-3.5 text-xs">
          <h2 className="font-bold text-zinc-200 mb-2.5 flex items-center justify-between">
            <span>Road Segment Status</span>
            <span className="text-[10px] font-normal text-zinc-500 uppercase">Backend Spec</span>
          </h2>

          <div className="space-y-1.5 mb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("OPEN") }} />
                <span className="text-zinc-300 font-medium">OPEN</span>
              </div>
              <span className="text-[11px] text-zinc-500">Passable</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("AT_RISK") }} />
                <span className="text-zinc-300 font-medium">AT_RISK</span>
              </div>
              <span className="text-[11px] text-zinc-500">Hazard / Weather caution</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("RESTRICTED") }} />
                <span className="text-zinc-300 font-medium">RESTRICTED</span>
              </div>
              <span className="text-[11px] text-zinc-500">Weight / access limits</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("BLOCKED") }} />
                <span className="text-zinc-300 font-medium">BLOCKED</span>
              </div>
              <span className="text-[11px] text-zinc-500">Hard closure</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: getStatusColor("UNKNOWN") }} />
                <span className="text-zinc-300 font-medium">UNKNOWN</span>
              </div>
              <span className="text-[11px] text-zinc-500">Unverified</span>
            </div>
          </div>

          <div className="pt-2.5 border-t border-zinc-800 text-[11px] text-zinc-400 space-y-1">
            <p className="text-amber-400/90 font-medium">
              ⚠️ Policy rule: UNKNOWN is never treated as safe or open.
            </p>
            <p className="text-zinc-500">
              Safety Score: 0–100 (100 safest). Disruption Probability: 0–1.
            </p>
          </div>
        </aside>

        {/* Selected Road Segment Inspector (if segment selected) */}
        {selectedRoad && (
          <aside className="absolute top-4 right-14 z-10 w-80 bg-zinc-900/95 border border-zinc-800 rounded-lg shadow-xl backdrop-blur p-4 text-xs">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800">
              <h2 className="font-bold text-zinc-200">Segment Inspector</h2>
              <button
                type="button"
                onClick={() => setSelectedRoad(null)}
                className="text-zinc-500 hover:text-zinc-300 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2">
              <div>
                <span className="text-zinc-500 text-[11px]">Name:</span>
                <p className="font-semibold text-zinc-200">{selectedRoad.name || "Unnamed Segment"}</p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-zinc-500 text-[11px]">Canonical ID:</span>
                  <p className="font-mono text-[11px] text-zinc-300">{selectedRoad.id}</p>
                </div>
                <div>
                  <span className="text-zinc-500 text-[11px]">Status:</span>
                  <p className="font-bold" style={{ color: getStatusColor(selectedRoad.status) }}>
                    {selectedRoad.status}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-zinc-500 text-[11px]">Road Class:</span>
                  <p className="capitalize text-zinc-300">{selectedRoad.road_class || "N/A"}</p>
                </div>
                <div>
                  <span className="text-zinc-500 text-[11px]">Length:</span>
                  <p className="text-zinc-300">
                    {selectedRoad.length_m ? `${(selectedRoad.length_m / 1000).toFixed(2)} km` : "N/A"}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800">
                <div>
                  <span className="text-zinc-500 text-[11px]">Safety Score:</span>
                  <p className="font-semibold text-zinc-200">
                    {selectedRoad.safety_score != null ? `${selectedRoad.safety_score.toFixed(1)} / 100` : "N/A"}
                  </p>
                </div>
                <div>
                  <span className="text-zinc-500 text-[11px]">Disruption Prob:</span>
                  <p className="font-semibold text-zinc-200">
                    {selectedRoad.disruption_probability != null
                      ? `${(selectedRoad.disruption_probability * 100).toFixed(1)}%`
                      : "Not evaluated"}
                  </p>
                </div>
              </div>

              {selectedRoad.status === "UNKNOWN" && (
                <div className="mt-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px]">
                  ⚠️ <strong>Unverified segment:</strong> Safety assessment pending backend operational evidence.
                </div>
              )}
            </div>
          </aside>
        )}
      </main>

      {/* Bottom Footer: Attribution Display */}
      <footer className="flex flex-wrap items-center justify-between px-5 py-2 border-t border-zinc-800 bg-zinc-950 text-[11px] text-zinc-400 z-20">
        <div>
          <span>{backendInfo?.attribution || "Road network data © OpenStreetMap contributors under ODbL"}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Map tiles © OpenStreetMap contributors</span>
          <span className="text-zinc-600">|</span>
          <span>Engine: MapLibre GL JS</span>
        </div>
      </footer>
    </div>
  );
}
