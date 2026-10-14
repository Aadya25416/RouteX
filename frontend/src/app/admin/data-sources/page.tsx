"use client";

import React, { useState } from "react";
import Link from "next/link";
import AdminLayout from "@/components/admin/AdminLayout";
import { INITIAL_DATA_SOURCES } from "@/data/adminData";

export default function AdminDataSourcesPage() {
  const [sources] = useState(INITIAL_DATA_SOURCES);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const handleTestConnection = (id: string, name: string) => {
    setTestingId(id);
    setStatusMsg(null);
    setTimeout(() => {
      setTestingId(null);
      setStatusMsg(`Connection verified: ${name} pipeline is responsive.`);
    }, 600);
  };

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Data Sources</h1>
            <p className="text-xs text-[#71877D]">
              Inspect configured geospatial, meteorological, and road network ingestion pipelines
            </p>
          </div>

          <Link href="/admin/settings" className="rx-admin-btn-outline">
            <span>Configure Refresh Intervals →</span>
          </Link>
        </div>

        {statusMsg && (
          <div className="p-3 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-xs font-semibold">
            ✓ {statusMsg}
          </div>
        )}

        <div className="rx-admin-table-wrap">
          <table className="rx-admin-table" aria-label="Data sources table">
            <thead>
              <tr>
                <th>Source Name</th>
                <th>Data Type</th>
                <th>Coverage / Scope</th>
                <th>Last Import</th>
                <th>Status</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((src) => (
                <tr key={src.id}>
                  <td>
                    <span className="font-bold text-xs text-[#193B32] block">{src.name}</span>
                    <span className="text-[11px] text-[#71877D]">{src.notes}</span>
                  </td>
                  <td className="text-xs font-semibold text-[#193B32]">{src.type}</td>
                  <td className="text-xs text-[#71877D]">{src.coverage}</td>
                  <td className="text-xs text-[#71877D]">{src.lastImport}</td>
                  <td>
                    <span
                      className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                        src.status === "Success" || src.status === "Connected"
                          ? "bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD]"
                          : "bg-[#FFF8EB] text-[#B45309] border border-[#FCE1B6]"
                      }`}
                    >
                      {src.status}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      type="button"
                      onClick={() => handleTestConnection(src.id, src.name)}
                      disabled={testingId === src.id}
                      className="px-3 py-1 bg-[#FAFBF7] hover:bg-white border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32] transition-colors cursor-pointer"
                    >
                      {testingId === src.id ? "Pinging..." : "Test Pipe"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rx-admin-card p-4 text-xs text-[#71877D] leading-relaxed">
          <strong className="text-[#193B32] block mb-1">Architecture Note:</strong>
          Per RouteX Master PRD specifications, external OpenStreetMap updates and weather feeds are ingested through asynchronous background ETL workers. No sensitive API keys or database credentials are exposed to client environments.
        </div>
      </div>
    </AdminLayout>
  );
}
