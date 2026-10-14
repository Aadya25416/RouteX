"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import AdminLayout from "@/components/admin/AdminLayout";
import { INITIAL_ADMIN_INCIDENTS } from "@/data/adminData";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

export default function AdminOverviewPage() {
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [incidents] = useState(INITIAL_ADMIN_INCIDENTS);

  useEffect(() => {
    fetch("/backend-api/info", { cache: "no-store" })
      .then((res) => {
        if (res.ok) {
          setIsBackendHealthy(true);
          return res.json();
        }
        setIsBackendHealthy(false);
        return null;
      })
      .then((data) => setBackendInfo(data))
      .catch(() => {
        setIsBackendHealthy(false);
      });

    fetch("/api/v1/roads/geojson?limit=500", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: RoadFeatureCollection | null) => {
        if (data && data.features) {
          setRoadsData(data);
        }
      })
      .catch(() => {});
  }, []);

  // Compute road segments count strictly from real data or baseline
  const segments = roadsData?.features || [];
  const totalCount = segments.length || 124;

  const openCount = segments.length
    ? segments.filter((f) => f.properties.status === "OPEN").length
    : 89;
  const atRiskCount = segments.length
    ? segments.filter((f) => f.properties.status === "AT_RISK").length
    : 18;
  const restrictedCount = segments.length
    ? segments.filter((f) => f.properties.status === "RESTRICTED").length
    : 5;
  const blockedCount = segments.length
    ? segments.filter((f) => f.properties.status === "BLOCKED").length
    : 6;
  const unknownCount = segments.length
    ? segments.filter((f) => f.properties.status === "UNKNOWN" || !f.properties.status).length
    : 6;

  // Percentage calculations
  const openPct = Math.round((openCount / totalCount) * 100);
  const atRiskPct = Math.round((atRiskCount / totalCount) * 100);
  const restrictedPct = Math.round((restrictedCount / totalCount) * 100);
  const blockedPct = Math.round((blockedCount / totalCount) * 100);
  const unknownPct = 100 - (openPct + atRiskPct + restrictedPct + blockedPct);

  return (
    <AdminLayout>
      <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full">
        {/* Top Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Overview</h1>
            <p className="text-xs text-[#71877D]">
              {backendInfo?.corridor?.name || "Guwahati–Tawang Corridor"} · Real-time operational intelligence
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              aria-label="Filter overview timeframe"
              defaultValue="today"
              className="appearance-none bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 pl-3 pr-7 rounded-full cursor-pointer focus:outline-none focus:border-[#16A779] shadow-xs"
            >
              <option value="today">Today</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
            <Link href="/admin/map" className="rx-admin-btn-primary">
              <span>View Live Map</span>
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        {/* Top Summary Cards (6 status categories + pending + users) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {/* Total Segments */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between">
            <div className="flex items-center justify-between text-[#71877D] text-xs mb-1">
              <span>Total Segments</span>
              <span>🛣️</span>
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{totalCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">Canonical graph</span>
          </div>

          {/* Open */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#16A779]">
            <div className="flex items-center justify-between text-[#16A779] text-xs font-bold mb-1">
              <span>Open</span>
              <span className="w-2 h-2 rounded-full bg-[#16A779]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{openCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">{openPct}% passable</span>
          </div>

          {/* At Risk */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#F4B64A]">
            <div className="flex items-center justify-between text-[#A66007] text-xs font-bold mb-1">
              <span>At Risk</span>
              <span className="w-2 h-2 rounded-full bg-[#F4B64A]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{atRiskCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">{atRiskPct}% caution</span>
          </div>

          {/* Restricted */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#F07838]">
            <div className="flex items-center justify-between text-[#C2410C] text-xs font-bold mb-1">
              <span>Restricted</span>
              <span className="w-2 h-2 rounded-full bg-[#F07838]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{restrictedCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">Weight/access limits</span>
          </div>

          {/* Blocked */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#DC4848]">
            <div className="flex items-center justify-between text-[#DC4848] text-xs font-bold mb-1">
              <span>Blocked</span>
              <span className="w-2 h-2 rounded-full bg-[#DC4848]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{blockedCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">Hard closure</span>
          </div>

          {/* Unknown */}
          <div className="rx-admin-card p-3.5 flex flex-col justify-between border-l-4 border-l-[#89939A]">
            <div className="flex items-center justify-between text-[#64748B] text-xs font-bold mb-1">
              <span>Unknown</span>
              <span className="w-2 h-2 rounded-full bg-[#89939A]" />
            </div>
            <span className="text-2xl font-extrabold text-[#193B32]">{unknownCount}</span>
            <span className="text-[10px] text-[#71877D] mt-1">Never treated as safe</span>
          </div>
        </div>

        {/* Middle Section: Road Status Distribution + Recent Incidents */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Road Status Distribution Card (5 cols) */}
          <div className="lg:col-span-5 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-[#193B32]">Road Status Distribution</h2>
                <span className="text-[10px] font-semibold text-[#71877D] px-2 py-0.5 rounded bg-[#FAFBF7] border border-[#DCE5D8]">
                  {roadsData ? "Live PostGIS Graph" : "Configured Baseline"}
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

          {/* Recent Incidents Card (7 cols) */}
          <div className="lg:col-span-7 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
                <h2 className="text-sm font-bold text-[#193B32]">Recent Incidents</h2>
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
        </div>

        {/* Bottom Section: System Health */}
        <div className="rx-admin-card">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#E8EFE5]">
            <h2 className="text-sm font-bold text-[#193B32]">System Health &amp; Ingestion Pipelines</h2>
            <span className="text-[11px] text-[#71877D]">
              FastAPI Engine: {backendInfo ? "v" + backendInfo.version : "Checking..."}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* API Server */}
            <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
              <span className={`w-3 h-3 rounded-full ${isBackendHealthy ? "bg-[#16A779]" : "bg-[#DC4848]"}`} />
              <div>
                <span className="text-xs font-bold text-[#193B32] block">API Server</span>
                <span className="text-[11px] text-[#71877D]">
                  {isBackendHealthy === null ? "Connecting..." : isBackendHealthy ? "Connected (Port 8000)" : "Offline (Fallback)"}
                </span>
              </div>
            </div>

            {/* Database */}
            <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
              <span className={`w-3 h-3 rounded-full ${isBackendHealthy ? "bg-[#16A779]" : "bg-[#F4B64A]"}`} />
              <div>
                <span className="text-xs font-bold text-[#193B32] block">PostGIS Database</span>
                <span className="text-[11px] text-[#71877D]">
                  {isBackendHealthy ? "Connected (Spatial)" : "Offline"}
                </span>
              </div>
            </div>

            {/* Road Data */}
            <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
              <span className="w-3 h-3 rounded-full bg-[#16A779]" />
              <div>
                <span className="text-xs font-bold text-[#193B32] block">Road Graph</span>
                <span className="text-[11px] text-[#71877D]">Last updated 2 days ago</span>
              </div>
            </div>

            {/* Incident Feed */}
            <div className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center gap-3">
              <span className="w-3 h-3 rounded-full bg-[#16A779]" />
              <div>
                <span className="text-xs font-bold text-[#193B32] block">Incident Feed</span>
                <span className="text-[11px] text-[#71877D]">Listening on /api/v1</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
