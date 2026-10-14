"use client";

import React, { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";

export default function AdminAnalyticsPage() {
  const [timeframe, setTimeframe] = useState("30d");
  const [isExporting, setIsExporting] = useState(false);

  const topRoutes = [
    { route: "NH-27 (Guwahati–Nagaon–Bomdila)", incidents: 12, riskLevel: "High" },
    { route: "SH-2 (Bomdila Pass Spur)", incidents: 5, riskLevel: "Medium" },
    { route: "NH-13 (Trans-Arunachal Connector)", incidents: 4, riskLevel: "Medium" },
    { route: "SH-1 (Tawang High Pass)", incidents: 3, riskLevel: "Low" },
  ];

  const handleExport = () => {
    setIsExporting(true);
    setTimeout(() => {
      setIsExporting(false);
      alert("Report compiled and ready for download: RouteX-Analytics-Corridor-Report.csv");
    }, 700);
  };

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Analytics &amp; Reports</h1>
            <p className="text-xs text-[#71877D]">
              Understand incident trends, road safety distribution, and corridor disruption patterns
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              aria-label="Select analytics timeframe"
              className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last Quarter</option>
            </select>

            <button
              type="button"
              onClick={handleExport}
              disabled={isExporting}
              className="rx-admin-btn-primary cursor-pointer"
            >
              <span>{isExporting ? "Compiling..." : "Export Report ↓"}</span>
            </button>
          </div>
        </div>

        {/* Top Grid: Trends Chart + Top Affected Routes */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Incident Trends SVG Area Chart (8 cols) */}
          <div className="lg:col-span-8 rx-admin-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-[#193B32]">Incident Trends</h2>
                <div className="flex items-center gap-3 text-[11px] font-semibold text-[#71877D]">
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#12432A]" /> Total</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#DC4848]" /> Landslide</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#F4B64A]" /> Road Block</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#0284C7]" /> Weather</span>
                </div>
              </div>

              {/* Scalable SVG Area Trend Chart */}
              <div className="w-full h-56 relative bg-[#FAFBF7] rounded-xl border border-[#DCE5D8] p-3 flex flex-col justify-end">
                <svg className="w-full h-full" viewBox="0 0 500 160" preserveAspectRatio="none">
                  {/* Grid lines */}
                  <line x1="0" y1="40" x2="500" y2="40" stroke="#E8EFE5" strokeDasharray="3 3" />
                  <line x1="0" y1="80" x2="500" y2="80" stroke="#E8EFE5" strokeDasharray="3 3" />
                  <line x1="0" y1="120" x2="500" y2="120" stroke="#E8EFE5" strokeDasharray="3 3" />

                  {/* Gradient Area Fill */}
                  <defs>
                    <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#16A779" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#16A779" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  <path
                    d="M0,130 Q70,90 140,110 T280,50 T420,80 L500,60 L500,160 L0,160 Z"
                    fill="url(#areaFill)"
                  />

                  {/* Total Line */}
                  <path
                    d="M0,130 Q70,90 140,110 T280,50 T420,80 L500,60"
                    fill="none"
                    stroke="#12432A"
                    strokeWidth="3"
                  />

                  {/* Landslide Line */}
                  <path
                    d="M0,145 Q70,120 140,135 T280,85 T420,110 L500,90"
                    fill="none"
                    stroke="#DC4848"
                    strokeWidth="2"
                    strokeDasharray="4 2"
                  />

                  {/* Weather Line */}
                  <path
                    d="M0,155 Q70,140 140,145 T280,120 T420,135 L500,125"
                    fill="none"
                    stroke="#0284C7"
                    strokeWidth="2"
                  />
                </svg>

                {/* X Axis Labels */}
                <div className="flex justify-between text-[10px] text-[#71877D] font-medium pt-2 border-t border-[#DCE5D8]">
                  <span>Apr 1</span>
                  <span>Apr 5</span>
                  <span>Apr 10</span>
                  <span>Apr 15</span>
                  <span>Apr 20</span>
                  <span>Apr 25</span>
                  <span>Apr 30</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-[#71877D] pt-3 mt-3 border-t border-[#E8EFE5]">
              Correlation note: Elevated landslide frequencies correlate with seasonal pre-monsoon precipitation spikes along the Bomdila ridge.
            </p>
          </div>

          {/* Top Affected Routes (4 cols) */}
          <div className="lg:col-span-4 rx-admin-card flex flex-col justify-between">
            <div>
              <h2 className="text-sm font-bold text-[#193B32] mb-3 pb-2 border-b border-[#E8EFE5]">
                Top Affected Routes
              </h2>

              <div className="space-y-3">
                {topRoutes.map((item) => (
                  <div
                    key={item.route}
                    className="p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8] flex items-center justify-between"
                  >
                    <div>
                      <span className="text-xs font-bold text-[#193B32] block">{item.route}</span>
                      <span className="text-[10px] text-[#71877D]">
                        Risk Level:{" "}
                        <strong
                          className={
                            item.riskLevel === "High"
                              ? "text-[#DC4848]"
                              : item.riskLevel === "Medium"
                              ? "text-[#F4B64A]"
                              : "text-[#16A779]"
                          }
                        >
                          {item.riskLevel}
                        </strong>
                      </span>
                    </div>
                    <span className="text-xs font-mono font-bold text-[#193B32] px-2.5 py-1 rounded-full bg-white border border-[#DCE5D8]">
                      {item.incidents} incidents
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-[11px] mt-4">
              <strong>Preventive Recommendation:</strong> Deploy stationary road patrol units at Bomdila spur junction during rainfall events.
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
