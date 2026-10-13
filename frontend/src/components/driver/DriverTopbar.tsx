"use client";

import React, { useState, useSyncExternalStore } from "react";
import Link from "next/link";

interface DriverTopbarProps {
  onSearch?: (query: string) => void;
}

function subscribeToStorage(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

export default function DriverTopbar({ onSearch }: DriverTopbarProps) {
  const [searchValue, setSearchValue] = useState("");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showNotification, setShowNotification] = useState(false);

  const driverLabel = useSyncExternalStore(
    subscribeToStorage,
    () => {
      const name = localStorage.getItem("rx_driver_name");
      if (name) return name;
      const email = localStorage.getItem("rx_driver_email");
      if (email) return email.split("@")[0];
      return "Driver";
    },
    () => "Driver"
  );

  const driverEmail = useSyncExternalStore(
    subscribeToStorage,
    () => localStorage.getItem("rx_driver_email") || "corridor-driver-01",
    () => "corridor-driver-01"
  );

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchValue(e.target.value);
    if (onSearch) {
      onSearch(e.target.value);
    }
  };

  return (
    <header className="rx-driver-topbar">
      <div className="rx-topbar-search">
        <svg
          className="rx-search-icon"
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
          placeholder="Search location, route or district..."
          value={searchValue}
          onChange={handleSearchChange}
          className="rx-topbar-search-input"
          aria-label="Search corridor locations"
        />

        <svg
          className="rx-search-caret"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      <div className="rx-topbar-right">
        {/* Notification Bell */}
        <div className="relative">
          <button
            type="button"
            className="rx-bell-btn"
            onClick={() => setShowNotification(!showNotification)}
            aria-label="Notifications"
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
            <span className="rx-bell-badge" />
          </button>

          {showNotification && (
            <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl p-3 shadow-xl border border-[#DCE5D8] z-50 text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#E8EFE5] font-semibold text-[#193B32]">
                <span>Corridor Alerts</span>
                <span className="text-[10px] text-[#71877D]">1 new</span>
              </div>
              <div className="mt-2.5 p-2 rounded-lg bg-[#FFF8EB] border border-[#FCE1B6] text-[#A66007]">
                <strong className="block text-[11px]">⚠️ Bomdila Alert</strong>
                Landslide risk active near NH-27 segment 4. Caution advised.
              </div>
            </div>
          )}
        </div>

        {/* Driver Profile Pill */}
        <div className="relative">
          <button
            type="button"
            className="rx-driver-profile-pill"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            aria-expanded={showProfileMenu}
            aria-label="Driver profile menu"
          >
            <span className="rx-driver-avatar">{driverLabel.charAt(0).toUpperCase()}</span>
            <span className="text-xs font-semibold text-[#193B32]">{driverLabel}</span>
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl py-1 shadow-xl border border-[#DCE5D8] z-50 text-xs">
              <div className="px-3 py-2 border-b border-[#E8EFE5]">
                <p className="font-semibold text-[#193B32]">{driverLabel}</p>
                <p className="text-[11px] text-[#71877D] truncate">{driverEmail}</p>
              </div>
              <Link
                href="/login"
                className="block px-3 py-2 text-[#DC4848] hover:bg-[#FEEEEE] transition-colors"
                onClick={() => {
                  setShowProfileMenu(false);
                  if (typeof window !== "undefined") {
                    localStorage.removeItem("rx_auth_role");
                    localStorage.removeItem("rx_driver_name");
                    localStorage.removeItem("rx_driver_email");
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
