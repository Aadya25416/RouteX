"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import AdminLayout from "@/components/admin/AdminLayout";
import AlertsPanel from "@/components/admin/AlertsPanel";
import { INITIAL_ADMIN_INCIDENTS } from "@/data/adminData";
import { api } from "@/lib/api";
import { connectEventStream, RouteXEvent } from "@/lib/events";
import type { AdminIncidentItem } from "@/types/admin";
import type { DashboardMetricsResponse } from "@/types/dashboard";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

interface IncidentListResponse {
  total: number;
  items: Array<{
    id: string;
    incident_type: string;
    status: string;
    severity?: string;
    description: string;
    location_description?: string;
    created_at: string;
  }>;
}

export default function AdminOverviewPage() {
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [dashboardMetrics, setDashboardMetrics] = useState<DashboardMetricsResponse | null>(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState<boolean>(true);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [incidents, setIncidents] = useState<AdminIncidentItem[]>(INITIAL_ADMIN_INCIDENTS);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [latestSseEvent, setLatestSseEvent] = useState<RouteXEvent | null>(null);

  const lastErrorRef = useRef<string | null>(null);

  const fetchDashboardMetrics = useCallback(async () => {
    try {
      const data = await api.get<DashboardMetricsResponse>("/api/v1/dashboard");
      setDashboardMetrics(data);
      setDashboardError(null);
      lastErrorRef.current = null;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard metrics";
      if (lastErrorRef.current !== msg) {
        console.warn("Live operational telemetry unavailable:", msg);
        lastErrorRef.current = msg;
      }
      setDashboardError(msg);
    } finally {
      setIsLoadingDashboard(false);
    }
  }, []);

  const fetchIncidents = useCallback(() => {
    api.get<IncidentListResponse>("/api/v1/incidents?limit=5")
      .then((res) => {
        if (res.items && res.items.length > 0) {
          const mapped: AdminIncidentItem[] = res.items.map((i) => ({
            id: i.id,
            type: (i.incident_type as AdminIncidentItem["type"]) || "OTHER",
            status: (i.status as AdminIncidentItem["status"]) || "SUBMITTED",
            location: i.location_description || "Corridor Segment",
            coordinates: [92.4, 27.2],
            reportedBy: "Operations Center",
            reporterRole: "Field Officer",
            description: i.description,
            timeAgo: new Date(i.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            timestamp: i.created_at || new Date().toISOString(),
            severity: (i.severity as AdminIncidentItem["severity"]) || "MEDIUM",
          }));
          setIncidents(mapped);
        }
      })
      .catch(() => {});
  }, []);

  const fetchRoads = useCallback(() => {
    api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
      .then((data) => {
        if (data && data.features) {
          setRoadsData(data);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;

    api.get<BackendInfoResponse>("/backend-api/info")
      .then((data) => {
        if (!active) return;
        setIsBackendHealthy(true);
        setBackendInfo(data);
      })
      .catch(() => {
        if (!active) return;
        setIsBackendHealthy(false);
      });

    const initLoad = async () => {
      try {
        const [dashRes, rRes, incRes] = await Promise.allSettled([
          api.get<DashboardMetricsResponse>("/api/v1/dashboard"),
          api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500"),
          api.get<IncidentListResponse>("/api/v1/incidents?limit=5"),
        ]);
        if (!active) return;

        if (dashRes.status === "fulfilled" && dashRes.value) {
          setDashboardMetrics(dashRes.value);
          setDashboardError(null);
          lastErrorRef.current = null;
        } else if (dashRes.status === "rejected") {
          const err = dashRes.reason;
          const msg = err instanceof Error ? err.message : "Failed to load dashboard metrics";
          if (lastErrorRef.current !== msg) {
            console.warn("Live operational telemetry unavailable:", msg);
            lastErrorRef.current = msg;
          }
          setDashboardError(msg);
        }

        if (rRes.status === "fulfilled" && rRes.value?.features) {
          setRoadsData(rRes.value);
        }

        if (incRes.status === "fulfilled" && incRes.value?.items && incRes.value.items.length > 0) {
          const mapped: AdminIncidentItem[] = incRes.value.items.map((i) => ({
            id: i.id,
            type: (i.incident_type as AdminIncidentItem["type"]) || "OTHER",
            status: (i.status as AdminIncidentItem["status"]) || "SUBMITTED",
            location: i.location_description || "Corridor Segment",
            coordinates: [92.4, 27.2],
            reportedBy: "Operations Center",
            reporterRole: "Field Officer",
            description: i.description,
            timeAgo: new Date(i.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            timestamp: i.created_at || new Date().toISOString(),
            severity: (i.severity as AdminIncidentItem["severity"]) || "MEDIUM",
          }));
          setIncidents(mapped);
        }
      } catch (err) {
        if (!active) return;
        setDashboardError(err instanceof Error ? err.message : "Failed to load dashboard metrics");
      } finally {
        if (!active) return;
        setIsLoadingDashboard(false);
      }
    };

    initLoad();

    // Periodic fallback polling (30s) if SSE disconnected
    const pollInterval = setInterval(() => {
      fetchDashboardMetrics();
    }, 30000);

    // Subscribe to SSE for live road, incident, trip, and alert events
    const unsubscribe = connectEventStream({
      onEvent: (event) => {
        setLatestSseEvent(event);
        if (event.event_type === "road.status_changed") {
          fetchRoads();
          fetchDashboardMetrics();
        } else if (event.event_type.startsWith("incident.")) {
          fetchIncidents();
          fetchDashboardMetrics();
        } else if (event.event_type.startsWith("trip.") || event.event_type.startsWith("alert.")) {
          fetchDashboardMetrics();
        }
      },
      onStatusChange: (status) => {
        setIsLiveConnected(status === "connected");
      },
    });

    return () => {
      active = false;
      clearInterval(pollInterval);
      unsubscribe();
    };
  }, [fetchDashboardMetrics, fetchRoads, fetchIncidents]);

  // Compute road segments count strictly from live dashboard metrics (or fallback to GeoJSON if pending)
  const totalRoads = dashboardMetrics?.roads.total ?? (roadsData?.features?.length || 0);
  const openCount = dashboardMetrics?.roads.open ?? 0;
  const atRiskCount = dashboardMetrics?.roads.at_risk ?? 0;
  const restrictedCount = dashboardMetrics?.roads.restricted ?? 0;
  const blockedCount = dashboardMetrics?.roads.blocked ?? 0;
  const unknownCount = dashboardMetrics?.roads.unknown ?? 0;

  // Percentage calculations with zero-division safety
  const openPct = totalRoads > 0 ? Math.round((openCount / totalRoads) * 100) : 0;
  const atRiskPct = totalRoads > 0 ? Math.round((atRiskCount / totalRoads) * 100) : 0;
  const restrictedPct = totalRoads > 0 ? Math.round((restrictedCount / totalRoads) * 100) : 0;
  const blockedPct = totalRoads > 0 ? Math.round((blockedCount / totalRoads) * 100) : 0;
  const unknownPct = totalRoads > 0 ? Math.max(0, 100 - (openPct + atRiskPct + restrictedPct + blockedPct)) : 0;

  return (
    <AdminLayout>
      <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full">
        {/* Top Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Overview</h1>
            <p className="text-xs text-[#71877D]">
              {dashboardMetrics?.corridor_name || backendInfo?.corridor?.name || "Guwahati–Tawang Corridor"} · Live operational intelligence
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border shadow-xs transition-colors ${
                isLiveConnected
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-slate-50 border-slate-200 text-slate-600"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isLiveConnected ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
                }`}
              />
              <span>{isLiveConnected ? "Real-Time Updates Active" : "Connecting..."}</span>
            </span>

            <button
              onClick={() => {
                fetchDashboardMetrics();
                fetchIncidents();
                fetchRoads();
              }}
              title="Refresh dashboard data"
              className="flex items-center gap-1 text-xs font-semibold text-[#193B32] bg-white border border-[#DCE5D8] px-3 py-1.5 rounded-full hover:bg-slate-50 shadow-xs"
            >
              <span>🔄</span>
              <span>Refresh</span>
            </button>

            <Link href="/admin/map" className="rx-admin-btn-primary">
              <span>View Live Map</span>
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        {/* Non-blocking warning banner if live telemetry is temporarily degraded */}
        {dashboardError && (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between text-xs text-amber-800 shadow-xs">
            <div className="flex items-center gap-2">
              <span className="text-sm">⚠️</span>
              <span>Operational telemetry temporarily unavailable ({dashboardError}). Active incidents and road network remain fully functional.</span>
            </div>
            <button
              onClick={fetchDashboardMetrics}
              className="px-3 py-1 bg-white border border-amber-300 rounded-lg font-bold text-amber-900 hover:bg-amber-100 transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Operational Telemetry Summary Row (Trips, Vehicles, Incidents, Alerts) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {/* Active Trips */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-t-4 border-t-[#16A779]">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span className="font-semibold">Active Trips</span>
              <span>🚚</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : dashboardMetrics?.trips.active_count ?? 0}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">
              {dashboardMetrics?.trips.recent_reroutes ? (
                <span className="text-amber-700 font-bold">
                  {dashboardMetrics.trips.recent_reroutes} recent reroutes
                </span>
              ) : (
                "0 reroutes past 24h"
              )}
            </span>
          </div>

          {/* Active Fleet */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-t-4 border-t-[#0284C7]">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span className="font-semibold">Fleet in Transit</span>
              <span>📡</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : `${dashboardMetrics?.vehicles.in_transit ?? 0} / ${dashboardMetrics?.vehicles.total ?? 0}`}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">
              {dashboardMetrics?.vehicles.live_tracking_active ?? 0} vehicles GPS live
            </span>
          </div>

          {/* Unresolved Incidents */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-t-4 border-t-[#DC4848]">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span className="font-semibold">Active Hazards</span>
              <span>⚠️</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : dashboardMetrics?.incidents.active_unresolved ?? 0}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">
              {dashboardMetrics?.incident_severities.critical ? (
                <span className="text-red-700 font-bold">
                  {dashboardMetrics.incident_severities.critical} critical severity
                </span>
              ) : (
                "No critical hazards"
              )}
            </span>
          </div>

          {/* Priority Deliveries */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-t-4 border-t-[#F07838]">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span className="font-semibold">Consignments</span>
              <span>📦</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : dashboardMetrics?.deliveries.in_transit ?? 0}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">
              {dashboardMetrics?.deliveries.priority_count ?? 0} high-priority
            </span>
          </div>
        </div>

        {/* Road Status Cards (6 status categories) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {/* Total Segments */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span>Total Segments</span>
              <span>🛣️</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : totalRoads}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">Database graph</span>
          </div>

          {/* Open */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#16A779]">
            <div className="flex items-center justify-between text-[#16A779] text-xs font-bold mb-1">
              <span>Open</span>
              <span className="w-2 h-2 rounded-full bg-[#16A779]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : openCount}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">{openPct}% passable</span>
          </div>

          {/* At Risk */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#F4B64A]">
            <div className="flex items-center justify-between text-[#A66007] text-xs font-bold mb-1">
              <span>At Risk</span>
              <span className="w-2 h-2 rounded-full bg-[#F4B64A]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : atRiskCount}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">{atRiskPct}% caution</span>
          </div>

          {/* Restricted */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#F07838]">
            <div className="flex items-center justify-between text-[#C2410C] text-xs font-bold mb-1">
              <span>Restricted</span>
              <span className="w-2 h-2 rounded-full bg-[#F07838]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : restrictedCount}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">Weight/access limits</span>
          </div>

          {/* Blocked */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#DC4848]">
            <div className="flex items-center justify-between text-[#DC4848] text-xs font-bold mb-1">
              <span>Blocked</span>
              <span className="w-2 h-2 rounded-full bg-[#DC4848]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : blockedCount}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">Hard closure</span>
          </div>

          {/* Unknown */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#89939A]">
            <div className="flex items-center justify-between text-[#64748B] text-xs font-bold mb-1">
              <span>Unknown</span>
              <span className="w-2 h-2 rounded-full bg-[#89939A]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">
              {isLoadingDashboard ? "..." : unknownCount}
            </span>
            <span className="text-[10px] text-[#71877D] mt-1">Never treated as safe</span>
          </div>
        </div>

        {/* Middle Section: Road Status Distribution + Real-Time Alerts Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Road Status Distribution Card (5 cols) */}
          <div className="lg:col-span-5 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-[#193B32]">Road Status Distribution</h2>
                <span className="text-[10px] font-semibold text-[#71877D] px-2 py-0.5 rounded bg-[#FAFBF7] border border-[#DCE5D8]">
                  {totalRoads > 0 ? "Live Database Graph" : "Graph Initializing"}
                </span>
              </div>

              {/* Segmented Distribution Bar */}
              <div className="w-full h-4 rounded-full overflow-hidden flex bg-gray-200 mb-6 shadow-inner">
                <div style={{ width: `${openPct}%` }} className="bg-[#16A779] transition-all" title={`Open: ${openPct}%`} />
                <div style={{ width: `${atRiskPct}%` }} className="bg-[#F4B64A] transition-all" title={`At Risk: ${atRiskPct}%`} />
                <div style={{ width: `${restrictedPct}%` }} className="bg-[#F07838] transition-all" title={`Restricted: ${restrictedPct}%`} />
                <div style={{ width: `${blockedPct}%` }} className="bg-[#DC4848] transition-all" title={`Blocked: ${blockedPct}%`} />
                <div style={{ width: `${unknownPct}%` }} className="bg-[#89939A] transition-all" title={`Unknown: ${unknownPct}%`} />
              </div>

              {/* Status Breakdown Legend */}
              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#16A779]" />
                    <span className="text-[#193B32] font-semibold">Open</span>
                  </div>
                  <span className="text-[#71877D] font-mono">{openPct}% ({openCount} segments)</span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#F4B64A]" />
                    <span className="text-[#193B32] font-semibold">At Risk</span>
                  </div>
                  <span className="text-[#71877D] font-mono">{atRiskPct}% ({atRiskCount} segments)</span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#F07838]" />
                    <span className="text-[#193B32] font-semibold">Restricted</span>
                  </div>
                  <span className="text-[#71877D] font-mono">{restrictedPct}% ({restrictedCount} segments)</span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#DC4848]" />
                    <span className="text-[#193B32] font-semibold">Blocked</span>
                  </div>
                  <span className="text-[#71877D] font-mono">{blockedPct}% ({blockedCount} segments)</span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#89939A]" />
                    <span className="text-[#193B32] font-semibold">Unknown</span>
                  </div>
                  <span className="text-[#71877D] font-mono">{unknownPct}% ({unknownCount} segments)</span>
                </div>
              </div>
            </div>

            <div className="pt-4 mt-4 border-t border-[#E8EFE5] text-[11px] text-[#A66007] bg-[#FFF8EB] p-2.5 rounded-xl border border-[#FCE1B6]">
              ⚠️ Policy rule: UNKNOWN segments require operational verification before routing heavy freight.
            </div>
          </div>

          {/* Actionable Alerts Panel (7 cols) */}
          <div className="lg:col-span-7">
            <AlertsPanel
              sseEvent={latestSseEvent}
              onAlertAcknowledged={fetchDashboardMetrics}
            />
          </div>
        </div>

        {/* Lower Section: Recent Incidents + System Health */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Recent Incidents Card (7 cols) */}
          <div className="lg:col-span-7 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
                <h2 className="text-sm font-bold text-[#193B32]">Recent Incident Reports</h2>
                <Link
                  href="/admin/incidents"
                  className="text-xs font-semibold text-[#16A779] hover:underline"
                >
                  View All Incidents →
                </Link>
              </div>

              <div className="divide-y divide-[#E8EFE5]">
                {incidents.slice(0, 4).map((inc) => (
                  <div key={inc.id} className="py-2.5 flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <span className="text-base mt-0.5">
                        {inc.type === "LANDSLIDE"
                          ? "⚠️"
                          : inc.type === "ROAD_COLLAPSE"
                          ? "🚫"
                          : inc.type === "FLASH_FLOOD"
                          ? "🌧️"
                          : "🛠️"}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[#193B32]">{inc.location}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              inc.status === "CONFIRMED"
                                ? "bg-[#DDF4E8] text-[#12432A]"
                                : inc.status === "UNDER_REVIEW"
                                ? "bg-[#E0F2FE] text-[#0284C7]"
                                : "bg-[#FFF8EB] text-[#B45309]"
                            }`}
                          >
                            {inc.status === "SUBMITTED" ? "Unverified" : inc.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-[#71877D] line-clamp-1 mt-0.5">
                          {inc.description}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] text-[#8F9E97] whitespace-nowrap">{inc.timeAgo}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-3 mt-3 border-t border-[#E8EFE5] flex items-center justify-between text-xs text-[#71877D]">
              <span>Active incident tracking on Guwahati–Tawang corridor</span>
              <Link href="/admin/field-reports" className="font-semibold text-[#176B4D] hover:underline">
                Inspect Field Reports
              </Link>
            </div>
          </div>

          {/* System Health & Ingestion Pipelines (5 cols) */}
          <div className="lg:col-span-5 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
                <h2 className="text-sm font-bold text-[#193B32]">System Telemetry</h2>
                <span className="text-[11px] text-[#71877D]">
                  FastAPI Engine: {backendInfo ? "v" + backendInfo.version : "Checking..."}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* API Server */}
                <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full shrink-0 ${isBackendHealthy ? "bg-[#16A779]" : "bg-[#DC4848]"}`} />
                  <div>
                    <span className="text-xs font-bold text-[#193B32] block">API Engine</span>
                    <span className="text-[10px] text-[#71877D]">
                      {isBackendHealthy === null ? "Connecting..." : isBackendHealthy ? "Operational (Port 8000)" : "Offline"}
                    </span>
                  </div>
                </div>

                {/* Database */}
                <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full shrink-0 ${isBackendHealthy ? "bg-[#16A779]" : "bg-[#F4B64A]"}`} />
                  <div>
                    <span className="text-xs font-bold text-[#193B32] block">PostGIS Database</span>
                    <span className="text-[10px] text-[#71877D]">
                      {isBackendHealthy ? "Connected (Spatial)" : "Offline"}
                    </span>
                  </div>
                </div>

                {/* Real-Time SSE Stream */}
                <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full shrink-0 ${isLiveConnected ? "bg-[#16A779]" : "bg-[#89939A]"}`} />
                  <div>
                    <span className="text-xs font-bold text-[#193B32] block">Redis SSE Stream</span>
                    <span className="text-[10px] text-[#71877D]">
                      {isLiveConnected ? "Streaming (Active)" : "Disconnected"}
                    </span>
                  </div>
                </div>

                {/* Active Alerts Count */}
                <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
                  <span className="w-3 h-3 rounded-full shrink-0 bg-[#16A779]" />
                  <div>
                    <span className="text-xs font-bold text-[#193B32] block">Alerts Pipeline</span>
                    <span className="text-[10px] text-[#71877D]">
                      {dashboardMetrics?.alerts.recent_count ?? 0} events past 24h
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-3 mt-3 border-t border-[#E8EFE5] text-[11px] text-[#71877D]">
              Corridor operational intelligence refreshed automatically via Redis event bus.
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
