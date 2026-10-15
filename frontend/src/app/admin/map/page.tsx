"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import AdminLayout from "@/components/admin/AdminLayout";
import { GUWAHATI_TAWANG_CORRIDOR_COORDS } from "@/data/driverData";
import { getStatusColor } from "@/components/RoadMap";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";
import { api } from "@/lib/api";
import { connectEventStream } from "@/lib/events";
import type { VehicleMarkerData } from "@/components/RoadMap";

interface VehicleItem {
  id: string;
  registration_number: string;
  vehicle_code?: string;
  status: string;
}

interface VehicleListRes {
  total: number;
  items: VehicleItem[];
}

// Dynamically import RoadMap
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center w-full h-full bg-[#EAF2E7] text-[#193B32] gap-3">
      <div className="w-8 h-8 border-3 border-[#16A779] border-t-transparent rounded-full animate-spin" />
      <p className="text-xs font-semibold">Initializing MapLibre road network engine...</p>
    </div>
  ),
});

export default function AdminLiveMapPage() {
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [selectedRoad, setSelectedRoad] = useState<RoadFeatureProperties | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [showUpdateModal, setShowUpdateModal] = useState<boolean>(false);
  const [vehicleMarkers, setVehicleMarkers] = useState<Map<string, VehicleMarkerData>>(new Map());
  const [liveUpdateNotice, setLiveUpdateNotice] = useState<string | null>(null);

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

    // Fetch initial fleet vehicles and their latest GPS locations
    api.get<VehicleListRes>("/api/v1/vehicles?limit=50")
      .then(async (res) => {
        if (!isMounted || !res?.items) return;
        const initialMap = new Map<string, VehicleMarkerData>();

        for (const veh of res.items) {
          try {
            const loc = await api.get<{
              latitude: number;
              longitude: number;
              speed_kmh?: number;
              heading_deg?: number;
              recorded_at: string;
            }>(`/api/v1/vehicles/${veh.id}/location`);

            if (loc && isMounted) {
              const recordedAt = new Date(loc.recorded_at).getTime();
              const isStale = (Date.now() - recordedAt) > 5 * 60 * 1000;
              initialMap.set(veh.id, {
                id: veh.id,
                lngLat: [loc.longitude, loc.latitude],
                label: veh.vehicle_code || veh.registration_number,
                speedKmh: loc.speed_kmh,
                heading: loc.heading_deg,
                isStale,
                updatedAt: loc.recorded_at,
              });
            }
          } catch {
            // Vehicle may not have telemetry yet
          }
        }

        if (isMounted) {
          setVehicleMarkers(new Map(initialMap));
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  // Connect to SSE stream for real-time corridor updates
  useEffect(() => {
    const unsubscribe = connectEventStream({
      onEvent: (event) => {
        if (event.event_type === "vehicle.location_updated") {
          const payload = event.payload;
          setVehicleMarkers((prev) => {
            const next = new Map(prev);
            const recordedAt = new Date(payload.recorded_at).getTime();
            const isStale = (Date.now() - recordedAt) > 5 * 60 * 1000;
            const label = payload.registration_number || payload.vehicle_code || prev.get(payload.vehicle_id)?.label || `Vehicle ${payload.vehicle_id.slice(0, 6)}`;

            next.set(payload.vehicle_id, {
              id: payload.vehicle_id,
              lngLat: [payload.longitude, payload.latitude],
              label,
              speedKmh: payload.speed_kmh,
              heading: payload.heading_deg,
              isStale,
              updatedAt: payload.recorded_at,
            });
            return next;
          });
        } else if (event.event_type === "road.status_changed") {
          api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
            .then(setRoadsData)
            .catch(() => {});
          setLiveUpdateNotice(`Road segment ${event.payload?.segment_id || ""} updated to ${event.payload?.status || ""}`);
          setTimeout(() => setLiveUpdateNotice(null), 5000);
        } else if (event.event_type === "trip.rerouted") {
          setLiveUpdateNotice(`Trip ${event.payload?.trip_id?.slice(0, 8)} rerouted (${event.payload?.reason || "hazard bypass"})`);
          setTimeout(() => setLiveUpdateNotice(null), 6000);
        }
      },
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Filtered roads collection if filter is active
  const filteredRoadsData = React.useMemo(() => {
    if (!roadsData || statusFilter === "ALL") return roadsData;
    return {
      type: "FeatureCollection" as const,
      features: roadsData.features.filter((f) => f.properties.status === statusFilter),
    };
  }, [roadsData, statusFilter]);

  // Default display segment if none selected
  const activeSegment: RoadFeatureProperties = selectedRoad || {
    id: "NH-27-1045",
    name: "NH-27 (Nagaon–Bomdila Connector)",
    road_class: "National Highway",
    length_m: 12400,
    oneway: false,
    status: "AT_RISK",
    safety_score: 62.0,
    disruption_probability: 0.45,
  };

  const stopMarkers = [
    { lngLat: [91.7362, 26.1445] as [number, number], label: "Guwahati" },
    { lngLat: [92.6842, 26.3452] as [number, number], label: "Nagaon" },
    { lngLat: [92.4159, 27.2645] as [number, number], label: "Bomdila", isNext: true },
    { lngLat: [91.8687, 27.5861] as [number, number], label: "Tawang", isDestination: true },
  ];

  const hazardMarker = {
    lngLat: [92.4159, 27.2645] as [number, number],
    label: "Landslide Report - Unverified",
    type: "landslide",
  };

  return (
    <AdminLayout>
      <div className="flex flex-col h-[calc(100vh-80px)] w-full gap-3">
        {/* Top Controls Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-extrabold text-[#193B32]">Live Map &amp; Road Network</h1>
            <p className="text-xs text-[#71877D]">
              Explore and manage canonical road segments across the corridor
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>{vehicleMarkers.size} Fleet Vehicles ({Array.from(vehicleMarkers.values()).filter((v) => !v.isStale).length} Live)</span>
            </span>

            <span className="text-xs font-semibold text-[#71877D] ml-2">Filter by Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter road network by segment status"
              className="bg-white border border-[#DCE5D8] text-xs font-bold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer focus:outline-none focus:border-[#16A779] shadow-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open Only</option>
              <option value="AT_RISK">At Risk</option>
              <option value="RESTRICTED">Restricted</option>
              <option value="BLOCKED">Blocked</option>
              <option value="UNKNOWN">Unknown</option>
            </select>
          </div>
        </div>

        {/* Real-time Event Notification Banner */}
        {liveUpdateNotice && (
          <div className="bg-[#EAF2E7] border border-[#16A779] text-[#12432A] px-4 py-2 rounded-xl text-xs font-semibold flex items-center justify-between shadow-xs animate-fadeIn">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#16A779] animate-ping" />
              <span>{liveUpdateNotice}</span>
            </div>
            <button
              type="button"
              onClick={() => setLiveUpdateNotice(null)}
              className="text-[#71877D] hover:text-[#193B32] font-bold text-xs"
            >
              ✕
            </button>
          </div>
        )}

        {/* Main Grid: Map Area + Segment Details Side Panel */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-0 overflow-hidden">
          {/* Map Column (8 or 9 cols) */}
          <div className="lg:col-span-8 xl:col-span-9 relative rx-admin-card p-0 overflow-hidden h-full min-h-[450px]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={filteredRoadsData}
              routeCoordinates={GUWAHATI_TAWANG_CORRIDOR_COORDS}
              stopMarkers={stopMarkers}
              hazardMarker={hazardMarker}
              vehicleMarkers={Array.from(vehicleMarkers.values())}
              onSelectRoad={setSelectedRoad}
              customCenter={[92.2, 26.9]}
              customZoom={8.0}
              className="w-full h-full relative"
            />

            {/* Floating Navigation ETA Pill Overlay */}
            <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
              <div className="bg-white/95 backdrop-blur-md px-3.5 py-2 rounded-xl shadow-lg border border-[#DCE5D8] flex items-center gap-2.5">
                <span className="text-base">🚗</span>
                <div>
                  <span className="text-xs font-bold text-[#193B32] block leading-tight">25 min</span>
                  <span className="text-[10px] text-[#71877D]">via NH-27 Corridor</span>
                </div>
              </div>
            </div>

            {/* Floating Road Status Legend */}
            <div className="absolute bottom-4 left-4 z-10 bg-white/95 backdrop-blur-md px-3.5 py-2.5 rounded-xl shadow-lg border border-[#DCE5D8] text-xs space-y-1">
              <span className="text-[10px] font-bold text-[#71877D] uppercase tracking-wider block mb-1">
                Status Legend
              </span>
              <div className="flex items-center gap-3 text-[11px] font-medium">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#16A779]" /> Open</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#F4B64A]" /> At Risk</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#F07838]" /> Restricted</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#DC4848]" /> Blocked</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#89939A]" /> Unknown</span>
              </div>
            </div>
          </div>

          {/* Right Segment Details Inspector (4 or 3 cols) */}
          <div className="lg:col-span-4 xl:col-span-3 rx-admin-card flex flex-col justify-between overflow-y-auto">
            <div className="space-y-4">
              <div className="pb-2 border-b border-[#E8EFE5] flex items-center justify-between">
                <div>
                  <h2 className="text-xs font-bold text-[#71877D] uppercase tracking-wider">
                    Segment Details
                  </h2>
                  <h3 className="text-sm font-extrabold text-[#193B32]">
                    {activeSegment.id}
                  </h3>
                </div>
                <span
                  className="text-xs font-bold px-2.5 py-0.5 rounded-full"
                  style={{
                    backgroundColor: `${getStatusColor(activeSegment.status)}20`,
                    color: getStatusColor(activeSegment.status),
                  }}
                >
                  {activeSegment.status}
                </span>
              </div>

              {/* Attributes Grid */}
              <div className="space-y-2.5 text-xs">
                <div>
                  <span className="text-[11px] text-[#71877D] block">Road Name</span>
                  <span className="font-bold text-[#193B32]">{activeSegment.name || "Unnamed Road"}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-[11px] text-[#71877D] block">Length</span>
                    <span className="font-bold text-[#193B32]">
                      {(activeSegment.length_m / 1000).toFixed(2)} km
                    </span>
                  </div>
                  <div>
                    <span className="text-[11px] text-[#71877D] block">Road Type</span>
                    <span className="font-bold text-[#193B32] capitalize">
                      {activeSegment.road_class || "Highway"}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#E8EFE5]">
                  <div>
                    <span className="text-[11px] text-[#71877D] block">Safety Score</span>
                    <span className="font-bold text-[#193B32]">
                      {activeSegment.safety_score != null ? `${activeSegment.safety_score}/100` : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[11px] text-[#71877D] block">Disruption Prob.</span>
                    <span className="font-bold text-[#193B32]">
                      {activeSegment.disruption_probability != null
                        ? `${(activeSegment.disruption_probability * 100).toFixed(0)}%`
                        : "None"}
                    </span>
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] text-[11px] text-[#71877D]">
                  <strong className="text-[#193B32] block mb-0.5">Canonical PostGIS Geometry</strong>
                  Integrated with live OpenStreetMap graph topology.
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="pt-4 border-t border-[#E8EFE5] flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setShowUpdateModal(true)}
                className="w-full py-2.5 px-4 bg-[#12432A] hover:bg-[#0b2f1c] text-white rounded-full text-xs font-bold transition-colors"
              >
                Update Status
              </button>

              <Link
                href="/map"
                className="w-full py-2 px-4 bg-white border border-[#DCE5D8] text-[#193B32] hover:bg-[#FAFBF7] rounded-full text-xs font-bold text-center transition-colors"
              >
                View on Full Map
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Honest Status Update Modal */}
      {showUpdateModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
        >
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl border border-[#DCE5D8]">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
              <h3 className="font-bold text-[#193B32] text-sm">
                Road Segment Status Control: {activeSegment.id}
              </h3>
              <button
                type="button"
                onClick={() => setShowUpdateModal(false)}
                className="text-[#71877D] hover:text-[#193B32] text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="text-xs text-[#71877D] space-y-3 mb-5 leading-relaxed">
              <p>
                In the RouteX architecture, road segment operational status (OPEN, AT_RISK, RESTRICTED, BLOCKED) is governed by <strong>verified incident confirmations</strong> and audited field evaluations to protect routing integrity.
              </p>
              <div className="p-3 rounded-xl bg-[#FFF8EB] border border-[#FCE1B6] text-[#A66007]">
                <strong>Audit Guard:</strong> Direct manual override requires elevated dispatcher authorization. To report or confirm a disruption on this segment, please use the Incident Management workflow.
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowUpdateModal(false)}
                className="px-4 py-2 border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32]"
              >
                Close
              </button>
              <Link
                href="/admin/incidents"
                className="px-4 py-2 bg-[#12432A] text-white rounded-full text-xs font-semibold"
                onClick={() => setShowUpdateModal(false)}
              >
                Go to Incident Review →
              </Link>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
