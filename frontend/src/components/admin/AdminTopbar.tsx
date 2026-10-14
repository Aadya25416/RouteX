"use client";

import React, { useState, useSyncExternalStore } from "react";
import Link from "next/link";

interface AdminTopbarProps {
  onSearch?: (query: string) => void;
}

function subscribeToStorage(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

export default function AdminTopbar({ onSearch }: AdminTopbarProps) {
  const [searchValue, setSearchValue] = useState("");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showNotification, setShowNotification] = useState(false);

  const adminName = useSyncExternalStore(
    subscribeToStorage,
    () => localStorage.getItem("rx_admin_name") || "System Admin",
    () => "System Admin"
  );

  const adminEmail = useSyncExternalStore(
    subscribeToStorage,
    () => localStorage.getItem("rx_admin_email") || "admin@routex.in",
    () => "admin@routex.in"
  );

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchValue(e.target.value);
    if (onSearch) {
      onSearch(e.target.value);
    }
  };

  return (
    <header className="rx-admin-topbar">
      {/* Search Input */}
      <div className="rx-admin-search">
        <svg
          className="rx-admin-search-icon"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>

        <input
          type="text"
          placeholder="Search location, road segment or incident..."
          value={searchValue}
          onChange={handleSearchChange}
          className="rx-admin-search-input"
          aria-label="Search corridor assets"
        />
      </div>

      <div className="rx-admin-topbar-right">
        {/* Notifications */}
        <div className="relative">
          <button
            type="button"
            className="rx-admin-bell-btn"
            onClick={() => setShowNotification(!showNotification)}
            aria-label="System Notifications"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            <span className="w-2 h-2 rounded-full bg-[#F4B64A] absolute top-2 right-2" />
          </button>

          {showNotification && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl p-3.5 shadow-xl border border-[#DCE5D8] z-50 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#E8EFE5] font-semibold text-[#193B32]">
                <span>Operational Alerts</span>
                <span className="text-[10px] text-[#71877D]">Live System Feed</span>
              </div>
              <div className="mt-2.5 space-y-2">
                <div className="p-2 rounded-lg bg-[#FFF8EB] border border-[#FCE1B6] text-[#A66007]">
                  <strong className="block text-[11px]">⚠️ NH-27 Landslide Caution</strong>
                  Unverified report near Dirang sector submitted by Field Officer.
                </div>
                <div className="p-2 rounded-lg bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A]">
                  <strong className="block text-[11px]">✓ OpenStreetMap Graph Sync</strong>
                  Canonical corridor geometry verified up to date.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Admin Profile Pill */}
        <div className="relative">
          <button
            type="button"
            className="rx-admin-profile-pill"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            aria-expanded={showProfileMenu}
            aria-label="Admin profile menu"
          >
            <span className="rx-admin-avatar">A</span>
            <div className="text-left flex flex-col leading-tight">
              <span className="text-xs font-bold text-[#193B32]">{adminName}</span>
              <span className="text-[10px] text-[#71877D] font-medium">System Admin</span>
            </div>
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="ml-1 text-[#71877D]"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-52 bg-white rounded-xl py-1 shadow-xl border border-[#DCE5D8] z-50 text-xs">
              <div className="px-3.5 py-2.5 border-b border-[#E8EFE5]">
                <p className="font-bold text-[#193B32]">{adminName}</p>
                <p className="text-[11px] text-[#71877D] truncate">{adminEmail}</p>
                <span className="inline-block mt-1 text-[10px] font-bold px-2 py-0.5 rounded bg-[#DDF4E8] text-[#12432A]">
                  Role: admin
                </span>
              </div>
              <Link
                href="/admin/settings"
                className="block px-3.5 py-2 text-[#193B32] hover:bg-[#F8FAF5] transition-colors"
                onClick={() => setShowProfileMenu(false)}
              >
                System Settings
              </Link>
              <Link
                href="/login"
                className="block px-3.5 py-2 text-[#DC4848] hover:bg-[#FEEEEE] transition-colors"
                onClick={() => {
                  setShowProfileMenu(false);
                  if (typeof window !== "undefined") {
                    localStorage.removeItem("rx_auth_role");
                    localStorage.removeItem("rx_admin_name");
                    localStorage.removeItem("rx_admin_email");
                  }
                }}
              >
                Switch Role / Logout
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
