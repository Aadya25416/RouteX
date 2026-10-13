"use client";

import React, { useState, useEffect } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { INITIAL_DELIVERIES } from "@/data/adminData";
import { DeliveryConsignment } from "@/types/admin";

interface BackendTripItem {
  id: string;
  delivery?: { origin_name?: string; destination_name?: string };
  driver_id?: string;
  vehicle?: { license_plate?: string };
  status?: string;
  completed_at?: string;
}

export default function AdminDeliveriesPage() {
  const [deliveries, setDeliveries] = useState<DeliveryConsignment[]>(INITIAL_DELIVERIES);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Connect to backend trips API if available
  useEffect(() => {
    fetch("/api/v1/trips?limit=50", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.items && data.items.length > 0) {
          const mapped: DeliveryConsignment[] = data.items.map((t: BackendTripItem) => ({
            id: `TR-${t.id.slice(0, 4).toUpperCase()}`,
            origin: t.delivery?.origin_name || "Guwahati",
            destination: t.delivery?.destination_name || "Tawang",
            driver: t.driver_id ? "Assigned Driver" : "Unassigned",
            vehicle: t.vehicle?.license_plate || "Freight Truck",
            status:
              t.status === "COMPLETED"
                ? "Completed"
                : t.status === "IN_TRANSIT"
                ? "In Progress"
                : "Assigned",
            etaOrCompleted: t.completed_at ? "Completed" : "Scheduled",
            priority: "HIGH",
          }));
          setDeliveries(mapped);
        }
      })
      .catch(() => {});
  }, []);

  const filtered = deliveries.filter((d) => {
    if (statusFilter !== "ALL" && d.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = d.id.toLowerCase().includes(q);
      const matchDriver = d.driver.toLowerCase().includes(q);
      const matchRoute = `${d.origin} ${d.destination}`.toLowerCase().includes(q);
      if (!matchId && !matchDriver && !matchRoute) return false;
    }
    return true;
  });

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        <div>
          <h1 className="text-xl font-extrabold text-[#193B32]">Deliveries &amp; Trips</h1>
          <p className="text-xs text-[#71877D]">
            Monitor assigned freight consignments, operational transit status, and driver schedules
          </p>
        </div>

        {/* Filters */}
        <div className="rx-admin-card p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-[#71877D]">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter deliveries by transit status"
              className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="In Progress">In Progress</option>
              <option value="Completed">Completed</option>
              <option value="Delayed">Delayed</option>
              <option value="Assigned">Assigned</option>
            </select>
          </div>

          <div className="relative w-full sm:w-64">
            <input
              type="text"
              placeholder="Search trips, drivers, routes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full py-1.5 pl-8 pr-3 text-xs bg-white border border-[#DCE5D8] rounded-full text-[#193B32] outline-none focus:border-[#16A779]"
            />
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-[#71877D]">🔍</span>
          </div>
        </div>

        {/* Deliveries Table */}
        <div className="rx-admin-table-wrap">
          <table className="rx-admin-table" aria-label="Deliveries and trips table">
            <thead>
              <tr>
                <th>Trip ID</th>
                <th>Route</th>
                <th>Assigned Driver</th>
                <th>Vehicle</th>
                <th>Status</th>
                <th>ETA / Completed</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => {
                let badgeClass = "bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD]";
                if (d.status === "In Progress") {
                  badgeClass = "bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD]";
                } else if (d.status === "Delayed") {
                  badgeClass = "bg-[#FFF8EB] text-[#B45309] border border-[#FCE1B6]";
                } else if (d.status === "Assigned") {
                  badgeClass = "bg-[#F1F5F9] text-[#475569] border border-[#CBD5E1]";
                }

                return (
                  <tr key={d.id}>
                    <td className="font-mono text-xs font-bold text-[#193B32]">{d.id}</td>
                    <td className="font-semibold text-xs text-[#193B32]">
                      {d.origin} → {d.destination}
                    </td>
                    <td>
                      <span className="font-semibold text-xs text-[#193B32]">{d.driver}</span>
                    </td>
                    <td className="font-mono text-xs text-[#71877D]">{d.vehicle}</td>
                    <td>
                      <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${badgeClass}`}>
                        {d.status}
                      </span>
                    </td>
                    <td className="text-xs text-[#71877D]">{d.etaOrCompleted}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}
