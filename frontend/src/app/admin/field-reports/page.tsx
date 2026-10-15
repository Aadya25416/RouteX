"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import AdminLayout from "@/components/admin/AdminLayout";
import { api } from "@/lib/api";
import { INITIAL_ADMIN_INCIDENTS } from "@/data/adminData";
import { AdminIncidentItem } from "@/types/admin";

interface BackendIncidentItem {
  id: string;
  incident_type?: "LANDSLIDE" | "ROAD_COLLAPSE" | "FLASH_FLOOD" | "BRIDGE_DAMAGE" | "OTHER";
  road_segment_id?: string;
  latitude?: number;
  longitude?: number;
  source?: string;
  observed_at?: string;
  created_at?: string;
  status?: "SUBMITTED" | "UNDER_REVIEW" | "CONFIRMED" | "REJECTED" | "RESOLVED";
  severity?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  description?: string;
}

interface IncidentListResponse {
  total: number;
  items: BackendIncidentItem[];
}

export default function FieldReportsPage() {
  const [reports, setReports] = useState<AdminIncidentItem[]>(INITIAL_ADMIN_INCIDENTS);
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");

  useEffect(() => {
    let isMounted = true;
    api
      .get<IncidentListResponse>("/api/v1/incidents?limit=50")
      .then((data) => {
        if (isMounted && data && data.items && data.items.length > 0) {
          const mapped: AdminIncidentItem[] = data.items.map((item: BackendIncidentItem) => ({
            id: item.id,
            type: item.incident_type || "LANDSLIDE",
            location: `Segment ${item.road_segment_id || "Corridor"} [${item.latitude?.toFixed(3)}, ${item.longitude?.toFixed(3)}]`,
            coordinates: [item.longitude || 92.4, item.latitude || 27.2],
            reportedBy: item.source === "FIELD_REPORT" ? "Field Officer" : "Driver Report",
            reporterRole: item.source === "FIELD_REPORT" ? "Field Officer" : "Driver",
            timeAgo: "Recently",
            timestamp: item.observed_at || item.created_at || new Date().toISOString(),
            status: item.status || "SUBMITTED",
            severity: item.severity || "HIGH",
            description: item.description || "Reported corridor condition",
            roadSegmentId: item.road_segment_id,
          }));
          setReports(mapped);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  const filtered = reports.filter((r) => {
    if (sourceFilter === "DRIVER" && r.reporterRole !== "Driver") return false;
    if (sourceFilter === "OFFICER" && r.reporterRole !== "Field Officer") return false;
    return true;
  });

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Field Reports</h1>
            <p className="text-xs text-[#71877D]">
              Direct submissions from mobile field crews and drivers requiring PostGIS segment confirmation
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              aria-label="Filter by report submitter role"
              className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
            >
              <option value="ALL">All Reporters</option>
              <option value="DRIVER">Driver Submissions</option>
              <option value="OFFICER">Field Officer Submissions</option>
            </select>
          </div>
        </div>

        <div className="rx-admin-table-wrap">
          <table className="rx-admin-table" aria-label="Field reports table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Incident Type</th>
                <th>Reported By</th>
                <th>Location Details</th>
                <th>Status</th>
                <th className="text-right">Audit</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td className="font-mono text-xs text-[#193B32] font-semibold">{r.id}</td>
                  <td className="font-bold text-[#193B32]">{r.type.replace("_", " ")}</td>
                  <td>
                    <span className="font-semibold block">{r.reportedBy}</span>
                    <span className="text-[10px] text-[#71877D]">{r.reporterRole}</span>
                  </td>
                  <td>
                    <span className="font-medium text-xs text-[#193B32]">{r.location}</span>
                    <p className="text-[11px] text-[#71877D] line-clamp-1">{r.description}</p>
                  </td>
                  <td>
                    <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#FFF8EB] text-[#B45309] border border-[#FCE1B6]">
                      {r.status === "SUBMITTED" ? "Unverified" : r.status}
                    </span>
                  </td>
                  <td className="text-right">
                    <Link
                      href="/admin/incidents"
                      className="px-3 py-1 bg-white border border-[#DCE5D8] hover:bg-[#FAFBF7] rounded-full text-xs font-semibold text-[#193B32] inline-block"
                    >
                      Inspect in Incidents →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}
