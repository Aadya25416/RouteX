"use client";

import React, { useState } from "react";
import Link from "next/link";
import DriverLayout from "@/components/driver/DriverLayout";
import { INITIAL_DRIVER_TRIP } from "@/data/driverData";

export default function TripCompletePage() {
  const [trip] = useState(INITIAL_DRIVER_TRIP);

  const completedStops = [
    { name: "Guwahati", time: "06:00 AM", statusText: "Departed" },
    { name: "Nagaon", time: "08:30 AM", statusText: "Reached" },
    { name: "Bomdila", time: "01:15 PM", statusText: "Reached" },
    { name: "Tawang", time: "08:45 PM", statusText: "Delivered" },
  ];

  return (
    <DriverLayout>
      <div className="max-w-5xl mx-auto w-full flex flex-col gap-6">
        {/* Page Heading */}
        <div className="text-center md:text-left">
          <h1 className="text-xl font-extrabold text-[#193B32]">Trip Summary &amp; Delivery Status</h1>
          <p className="text-xs text-[#71877D]">
            Review completed delivery log and verified operational milestones.
          </p>
        </div>

        {/* Two-Column Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Card: Delivery Confirmation & Completed Stops */}
          <div className="md:col-span-6 rx-card flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3.5 mb-4">
                <div className="w-12 h-12 rounded-full bg-[#DDF4E8] border border-[#B7E4CD] flex items-center justify-center text-[#16A779] text-2xl shadow-xs">
                  ✓
                </div>
                <div>
                  <h2 className="text-lg font-extrabold text-[#193B32]">Trip Completed</h2>
                  <p className="text-xs font-semibold text-[#16A779]">
                    {trip.origin} → {trip.destination}
                  </p>
                  <p className="text-[11px] text-[#71877D]">Delivered successfully</p>
                </div>
              </div>

              <div className="pt-4 border-t border-[#E8EFE5]">
                <h3 className="text-xs font-bold text-[#71877D] uppercase tracking-wider mb-3">
                  Completed Stops
                </h3>
                <div className="space-y-3.5 pl-2 relative before:absolute before:left-[13px] before:top-2 before:bottom-2 before:w-[2px] before:bg-[#DDF4E8]">
                  {completedStops.map((stop) => (
                    <div key={stop.name} className="relative flex items-center justify-between pl-6">
                      <span className="absolute left-[3px] top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#16A779] ring-4 ring-white" />
                      <div>
                        <span className="text-xs font-bold text-[#193B32] block">{stop.name}</span>
                        <span className="text-[11px] text-[#71877D]">{stop.time}</span>
                      </div>
                      <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-[#DDF4E8] text-[#12432A]">
                        {stop.statusText}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-4 mt-6 border-t border-[#E8EFE5] text-[11px] text-[#71877D] flex justify-between">
              <span>Trip Reference:</span>
              <span className="font-mono text-[#193B32]">{trip.id}</span>
            </div>
          </div>

          {/* Right Card: Metrics & Safety Audit */}
          <div className="md:col-span-6 rx-card flex flex-col justify-between">
            <div>
              <h2 className="text-base font-extrabold text-[#193B32] mb-4">Trip Summary</h2>

              <div className="space-y-3">
                {/* Total Distance */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8]">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">🛣️</span>
                    <div>
                      <span className="text-xs font-bold text-[#193B32] block">Total Distance</span>
                      <span className="text-[10px] text-[#71877D]">Guwahati–Tawang Corridor</span>
                    </div>
                  </div>
                  <span className="text-sm font-bold text-[#193B32]">{trip.totalDistanceKm} km</span>
                </div>

                {/* Total Time */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8]">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">⏱️</span>
                    <div>
                      <span className="text-xs font-bold text-[#193B32] block">Total Travel Time</span>
                      <span className="text-[10px] text-[#71877D]">Includes transit stops</span>
                    </div>
                  </div>
                  <span className="text-sm font-bold text-[#193B32]">{trip.actualDuration || "12 hr 45 min"}</span>
                </div>

                {/* Vehicle */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8]">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">🚛</span>
                    <div>
                      <span className="text-xs font-bold text-[#193B32] block">Vehicle</span>
                      <span className="text-[10px] text-[#71877D]">Freight Transport</span>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-[#193B32]">{trip.vehicleNumber}</span>
                </div>

                {/* Status */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#FAFBF7] border border-[#DCE5D8]">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">📋</span>
                    <div>
                      <span className="text-xs font-bold text-[#193B32] block">Status</span>
                      <span className="text-[10px] text-[#71877D]">Dispatch verification</span>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-[#16A779] px-2.5 py-0.5 rounded-full bg-[#DDF4E8]">
                    Completed
                  </span>
                </div>
              </div>
            </div>

            {/* Green Audit Callout */}
            <div className="mt-4 p-3.5 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-xs">
              <div className="flex items-center gap-2 font-bold mb-0.5">
                <span>✓</span>
                <span>Corridor Safety Cleared</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                No active incidents on this trip. Thank you for a safe delivery across the Northeast corridor!
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons Row */}
        <div className="flex flex-wrap items-center justify-center sm:justify-end gap-3 pt-2">
          <Link href="/driver/navigation" className="rx-btn-outline">
            <span>View Route Details</span>
          </Link>

          <Link
            href="/driver/report-incident"
            className="px-5 py-2.5 rounded-full bg-[#FFF8EB] hover:bg-[#FCE1B6] border border-[#FCE1B6] text-[#A66007] text-xs font-bold flex items-center gap-1.5 transition-colors"
          >
            <span>⚠️</span>
            <span>Report an Issue</span>
          </Link>

          <Link href="/driver" className="rx-btn-primary">
            <span>Back to Dashboard</span>
          </Link>
        </div>
      </div>
    </DriverLayout>
  );
}
