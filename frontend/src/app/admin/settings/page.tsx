"use client";

import React, { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";

export default function AdminSettingsPage() {
  const [dataRefreshInterval, setDataRefreshInterval] = useState("15");
  const [enableAlertSound, setEnableAlertSound] = useState(true);
  const [autoCenterIncident, setAutoCenterIncident] = useState(true);
  const [savedMsg, setSavedMsg] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg(true);
    setTimeout(() => setSavedMsg(false), 3000);
  };

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-4xl mx-auto w-full">
        <div>
          <h1 className="text-xl font-extrabold text-[#193B32]">System Settings</h1>
          <p className="text-xs text-[#71877D]">
            Manage application parameters, polling intervals, and notification preferences
          </p>
        </div>

        {savedMsg && (
          <div className="p-3 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-xs font-semibold">
            ✓ System preferences successfully updated.
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          {/* 1. Data Refresh & Polling */}
          <div className="rx-admin-card p-5 space-y-3">
            <h2 className="text-sm font-bold text-[#193B32]">Data Refresh &amp; Polling Intervals</h2>
            <p className="text-xs text-[#71877D]">
              Configure automated background queries for new incident reports and road segment status transitions.
            </p>

            <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <label htmlFor="refresh-interval-select" className="text-xs font-bold text-[#193B32]">
                Road Network &amp; Incident Polling:
              </label>
              <select
                id="refresh-interval-select"
                value={dataRefreshInterval}
                onChange={(e) => setDataRefreshInterval(e.target.value)}
                className="bg-white border border-[#DCE5D8] rounded-xl text-xs font-semibold text-[#193B32] p-2 outline-none focus:border-[#16A779]"
              >
                <option value="5">Every 5 minutes (Aggressive)</option>
                <option value="15">Every 15 minutes (Standard)</option>
                <option value="30">Every 30 minutes (Bandwidth Saving)</option>
                <option value="60">Every 1 hour (Low Frequency)</option>
              </select>
            </div>
          </div>

          {/* 2. Notification Preferences */}
          <div className="rx-admin-card p-5 space-y-3">
            <h2 className="text-sm font-bold text-[#193B32]">Notification &amp; Alert Preferences</h2>
            <div className="space-y-2.5 pt-1 text-xs">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableAlertSound}
                  onChange={(e) => setEnableAlertSound(e.target.checked)}
                  className="rounded text-[#16A779] focus:ring-[#16A779]"
                />
                <span className="font-semibold text-[#193B32]">
                  Audio alerts on incoming critical road blockages
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoCenterIncident}
                  onChange={(e) => setAutoCenterIncident(e.target.checked)}
                  className="rounded text-[#16A779] focus:ring-[#16A779]"
                />
                <span className="font-semibold text-[#193B32]">
                  Auto-focus MapLibre viewport when clicking incident alerts
                </span>
              </label>
            </div>
          </div>

          {/* 3. System Environment Info */}
          <div className="rx-admin-card p-5 space-y-2 text-xs">
            <h2 className="text-sm font-bold text-[#193B32]">System Environment &amp; Version</h2>
            <div className="grid grid-cols-2 gap-3 pt-1 text-[#71877D]">
              <div>Environment: <strong className="text-[#193B32]">Phase 1 Prototype</strong></div>
              <div>Platform: <strong className="text-[#193B32]">RouteX / NER-LINK</strong></div>
              <div>Mapping Engine: <strong className="text-[#193B32]">MapLibre GL JS v6.14</strong></div>
              <div>Coordinate Reference: <strong className="text-[#193B32]">WGS84 (EPSG:4326)</strong></div>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button type="submit" className="rx-admin-btn-primary cursor-pointer">
              <span>Save System Settings</span>
            </button>
          </div>
        </form>
      </div>
    </AdminLayout>
  );
}
