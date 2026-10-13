"use client";

import React, { useState, useEffect } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { INITIAL_ADMIN_INCIDENTS } from "@/data/adminData";
import { AdminIncidentItem, AdminIncidentStatus } from "@/types/admin";

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

export default function IncidentManagementPage() {
  const [incidents, setIncidents] = useState<AdminIncidentItem[]>(INITIAL_ADMIN_INCIDENTS);
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedIncident, setSelectedIncident] = useState<AdminIncidentItem | null>(null);
  const [reviewNote, setReviewNote] = useState<string>("");
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // Fetch real incidents if backend is reachable
  useEffect(() => {
    fetch("/api/v1/incidents?limit=50", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.items && data.items.length > 0) {
          const mapped: AdminIncidentItem[] = data.items.map((item: BackendIncidentItem) => ({
            id: item.id,
            type: item.incident_type || "LANDSLIDE",
            location: `Segment ${item.road_segment_id || "Corridor"} [${item.latitude?.toFixed(3)}, ${item.longitude?.toFixed(3)}]`,
            coordinates: [item.longitude || 92.4, item.latitude || 27.2],
            reportedBy: item.source === "FIELD_REPORT" ? "Field Officer" : "Driver Report",
            reporterRole: item.source === "FIELD_REPORT" ? "Field Officer" : "Driver",
            timeAgo: "Recently",
            timestamp: item.observed_at || item.created_at,
            status: item.status || "SUBMITTED",
            severity: item.severity || "HIGH",
            description: item.description || "Reported corridor condition",
            roadSegmentId: item.road_segment_id,
          }));
          setIncidents(mapped);
        }
      })
      .catch(() => {});
  }, []);

  const filteredIncidents = incidents.filter((inc) => {
    if (typeFilter !== "ALL" && inc.type !== typeFilter) return false;
    if (statusFilter !== "ALL" && inc.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchLoc = inc.location.toLowerCase().includes(q);
      const matchDesc = inc.description.toLowerCase().includes(q);
      const matchUser = inc.reportedBy.toLowerCase().includes(q);
      if (!matchLoc && !matchDesc && !matchUser) return false;
    }
    return true;
  });

  const handleUpdateStatus = async (newStatus: AdminIncidentStatus) => {
    if (!selectedIncident) return;

    // Update in local state
    setIncidents((prev) =>
      prev.map((i) =>
        i.id === selectedIncident.id
          ? { ...i, status: newStatus, reviewNotes: reviewNote || i.reviewNotes }
          : i
      )
    );

    // Attempt backend update
    try {
      const endpointMap: { [key: string]: string } = {
        CONFIRMED: `/api/v1/incidents/${selectedIncident.id}/confirm`,
        REJECTED: `/api/v1/incidents/${selectedIncident.id}/reject`,
        UNDER_REVIEW: `/api/v1/incidents/${selectedIncident.id}/review`,
        RESOLVED: `/api/v1/incidents/${selectedIncident.id}/resolve`,
      };
      const endpoint = endpointMap[newStatus];
      if (endpoint) {
        await fetch(endpoint, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ review_notes: reviewNote }),
        });
      }
    } catch {
      // Handled locally
    }

    setActionSuccessMsg(`Incident ${selectedIncident.id} updated to status "${newStatus}".`);
    setSelectedIncident(null);
    setReviewNote("");
    setTimeout(() => setActionSuccessMsg(null), 4000);
  };

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Incident Management</h1>
            <p className="text-xs text-[#71877D]">
              Review, verify, and resolve operational road hazards reported across the corridor
            </p>
          </div>
        </div>

        {actionSuccessMsg && (
          <div className="p-3 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-xs font-semibold flex items-center justify-between">
            <span>✓ {actionSuccessMsg}</span>
            <button type="button" onClick={() => setActionSuccessMsg(null)} className="text-sm font-bold">✕</button>
          </div>
        )}

        {/* Filter Controls Row */}
        <div className="rx-admin-card p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by incident type"
              className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
            >
              <option value="ALL">All Types</option>
              <option value="LANDSLIDE">Landslides</option>
              <option value="ROAD_COLLAPSE">Road Blocks</option>
              <option value="FLASH_FLOOD">Weather Issues</option>
              <option value="BRIDGE_DAMAGE">Bridge Issues</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by incident status"
              className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="SUBMITTED">Unverified (Pending)</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="REJECTED">Rejected</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              placeholder="Search incidents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full py-1.5 pl-8 pr-3 text-xs bg-white border border-[#DCE5D8] rounded-full text-[#193B32] outline-none focus:border-[#16A779]"
            />
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-[#71877D]">🔍</span>
          </div>
        </div>

        {/* Incidents Table */}
        <div className="rx-admin-table-wrap">
          <table className="rx-admin-table" aria-label="Incidents table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Location</th>
                <th>Reported By</th>
                <th>Time</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-xs text-[#71877D]">
                    No incident reports match the selected filters.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => {
                  let statusBadge = "bg-[#FFF8EB] text-[#B45309] border border-[#FCE1B6]";
                  let statusLabel = "Unverified";

                  if (inc.status === "CONFIRMED") {
                    statusBadge = "bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD]";
                    statusLabel = "Confirmed";
                  } else if (inc.status === "UNDER_REVIEW") {
                    statusBadge = "bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD]";
                    statusLabel = "Under Review";
                  } else if (inc.status === "REJECTED") {
                    statusBadge = "bg-[#FEEEEE] text-[#DC4848] border border-[#FCA5A5]";
                    statusLabel = "Rejected";
                  } else if (inc.status === "RESOLVED") {
                    statusBadge = "bg-[#F1F5F9] text-[#475569] border border-[#CBD5E1]";
                    statusLabel = "Resolved";
                  }

                  return (
                    <tr key={inc.id}>
                      <td className="font-bold text-[#193B32]">
                        <span className="mr-1.5">
                          {inc.type === "LANDSLIDE"
                            ? "⚠️"
                            : inc.type === "ROAD_COLLAPSE"
                            ? "🚫"
                            : inc.type === "FLASH_FLOOD"
                            ? "🌧️"
                            : "🛠️"}
                        </span>
                        {inc.type.replace("_", " ")}
                      </td>
                      <td>
                        <span className="font-semibold block">{inc.location}</span>
                        <span className="text-[11px] text-[#71877D] line-clamp-1">
                          {inc.description}
                        </span>
                      </td>
                      <td>
                        <span className="font-semibold block">{inc.reportedBy}</span>
                        <span className="text-[10px] text-[#71877D]">{inc.reporterRole}</span>
                      </td>
                      <td className="text-[#71877D] whitespace-nowrap">{inc.timeAgo}</td>
                      <td>
                        <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${statusBadge}`}>
                          {statusLabel}
                        </span>
                      </td>
                      <td className="text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedIncident(inc);
                            setReviewNote(inc.reviewNotes || "");
                          }}
                          className="px-3 py-1 bg-[#12432A] hover:bg-[#0b2f1c] text-white rounded-full text-xs font-semibold transition-colors cursor-pointer"
                        >
                          Review
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Review Modal / Drawer */}
        {selectedIncident && (
          <div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
          >
            <div className="bg-white rounded-2xl p-6 max-w-lg w-full shadow-2xl border border-[#DCE5D8]">
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#E8EFE5]">
                <div>
                  <h3 className="font-extrabold text-[#193B32] text-sm">
                    Review Incident Report: {selectedIncident.id}
                  </h3>
                  <span className="text-xs text-[#71877D]">
                    Reported by {selectedIncident.reportedBy} ({selectedIncident.reporterRole})
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedIncident(null)}
                  className="text-[#71877D] hover:text-[#193B32] text-lg font-bold"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs mb-5">
                <div>
                  <span className="text-[11px] text-[#71877D] block">Location &amp; Coordinates</span>
                  <span className="font-bold text-[#193B32]">{selectedIncident.location}</span>
                  <span className="font-mono text-[11px] text-[#71877D] block">
                    [{selectedIncident.coordinates[1].toFixed(4)}, {selectedIncident.coordinates[0].toFixed(4)}]
                  </span>
                </div>

                <div>
                  <span className="text-[11px] text-[#71877D] block">Field Description</span>
                  <p className="p-2.5 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] text-[#193B32] leading-relaxed">
                    {selectedIncident.description}
                  </p>
                </div>

                <div>
                  <label htmlFor="review-note" className="text-[11px] font-bold text-[#193B32] block mb-1">
                    Review / Dispatch Notes
                  </label>
                  <textarea
                    id="review-note"
                    rows={2}
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    placeholder="Add operational notes or instructions for field crew..."
                    className="w-full p-2.5 text-xs bg-white border border-[#DCE5D8] rounded-xl text-[#193B32] outline-none focus:border-[#16A779]"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-[#E8EFE5]">
                <button
                  type="button"
                  onClick={() => handleUpdateStatus("REJECTED")}
                  className="px-3.5 py-1.5 rounded-full border border-[#FCA5A5] bg-[#FEEEEE] text-[#DC4848] text-xs font-bold hover:bg-red-100 transition-colors cursor-pointer"
                >
                  Reject Report
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleUpdateStatus("UNDER_REVIEW")}
                    className="px-3.5 py-1.5 rounded-full border border-[#BAE6FD] bg-[#E0F2FE] text-[#0284C7] text-xs font-bold hover:bg-blue-100 transition-colors cursor-pointer"
                  >
                    Mark Under Review
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUpdateStatus("CONFIRMED")}
                    className="px-4 py-1.5 rounded-full bg-[#12432A] text-white text-xs font-bold hover:bg-[#0b2f1c] transition-colors cursor-pointer"
                  >
                    Confirm Hazard ✓
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
