"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

// Crisp SVG Icons matching the reference design
function IconDashboard() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function IconMyRoute() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="6" cy="19" r="3" />
      <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
      <circle cx="18" cy="5" r="3" />
    </svg>
  );
}

function IconLiveLocation() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}

function IconReportIncident() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconMessages() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function IconProfile() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M20 21a8 8 0 1 0-16 0" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export default function DriverSidebar() {
  const pathname = usePathname();
  const [modalNotice, setModalNotice] = useState<string | null>(null);

  const isDashboardActive = pathname === "/driver" || pathname === "/driver/trip-complete";
  const isNavigationActive = pathname === "/driver/navigation";
  const isReportActive = pathname === "/driver/report-incident";

  return (
    <>
      <aside className="rx-driver-sidebar" aria-label="Driver Navigation">
        <div>
          <Link href="/driver" className="rx-driver-logo" aria-label="RouteX Driver Portal">
            <span className="rx-driver-logo-name">Route</span>
            <span className="rx-driver-logo-x">X</span>
          </Link>

          <nav className="rx-sidebar-nav" aria-label="Main driver menu">
            <Link
              href="/driver"
              className={`rx-sidebar-link ${isDashboardActive ? "active" : ""}`}
              aria-current={pathname === "/driver" ? "page" : undefined}
            >
              <IconDashboard />
              <span className="rx-sidebar-text">Dashboard</span>
            </Link>

            <Link
              href="/driver"
              className={`rx-sidebar-link ${pathname === "/driver" ? "active" : ""}`}
            >
              <IconMyRoute />
              <span className="rx-sidebar-text">My Route</span>
            </Link>

            <Link
              href="/driver/navigation"
              className={`rx-sidebar-link ${isNavigationActive ? "active" : ""}`}
              aria-current={isNavigationActive ? "page" : undefined}
            >
              <IconLiveLocation />
              <span className="rx-sidebar-text">Live Location</span>
            </Link>

            <Link
              href="/driver/report-incident"
              className={`rx-sidebar-link ${isReportActive ? "active" : ""}`}
              aria-current={isReportActive ? "page" : undefined}
            >
              <IconReportIncident />
              <span className="rx-sidebar-text">Report Incident</span>
            </Link>

            <button
              type="button"
              className="rx-sidebar-link"
              onClick={() => setModalNotice("Driver messaging & dispatch communications are scheduled for Phase 2.")}
            >
              <IconMessages />
              <span className="rx-sidebar-text">Messages</span>
            </button>
          </nav>
        </div>

        <div className="rx-sidebar-bottom">
          <button
            type="button"
            className="rx-sidebar-link"
            onClick={() => setModalNotice("Driver profile & license verification details are managed by logistics dispatch.")}
          >
            <IconProfile />
            <span className="rx-sidebar-text">Profile</span>
          </button>

          <button
            type="button"
            className="rx-sidebar-link"
            onClick={() => setModalNotice("App settings & offline offline map cache controls are coming soon.")}
          >
            <IconSettings />
            <span className="rx-sidebar-text">Settings</span>
          </button>
        </div>
      </aside>

      {modalNotice && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4"
        >
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl border border-[#DCE5D8]">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-[#193B32] text-sm">Feature Information</h3>
              <button
                type="button"
                onClick={() => setModalNotice(null)}
                className="text-[#71877D] hover:text-[#193B32] text-lg font-bold"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-[#71877D] mb-5 leading-relaxed">{modalNotice}</p>
            <button
              type="button"
              onClick={() => setModalNotice(null)}
              className="w-full py-2 bg-[#12432A] text-white rounded-full text-xs font-semibold hover:bg-[#0d3420]"
            >
              Understood
            </button>
          </div>
        </div>
      )}
    </>
  );
}
