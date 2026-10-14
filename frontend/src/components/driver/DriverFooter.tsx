import React from "react";
import Link from "next/link";

const CURRENT_YEAR = 2026;

export default function DriverFooter() {
  return (
    <footer
      className="mt-auto border-t border-[#DCE5D8] bg-[#FAFBF7]/95 backdrop-blur-xs px-6 py-3 text-xs text-[#71877D] transition-colors"
      role="contentinfo"
      aria-label="Driver portal footer"
    >
      <div className="w-full flex flex-col gap-2.5">
        {/* Tier 1: Brand & Context (Left) + Dispatch Status (Right) */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-[#E8EFE5] pb-2.5">
          <div className="flex items-center flex-wrap gap-2">
            <Link
              href="/driver"
              className="font-black text-sm tracking-tight text-[#193B32] hover:text-[#16A779] transition-colors focus-visible:outline-2 focus-visible:outline-[#16A779] focus-visible:outline-offset-2 rounded"
              aria-label="RouteX Driver Portal"
            >
              <span>Route</span>
              <span className="text-[#16A779]">X</span>
            </Link>
            <span className="text-[10px] font-bold uppercase bg-[#DDF4E8] text-[#12432A] px-1.5 py-0.5 rounded tracking-wide">
              Driver Portal
            </span>
            <span className="text-[#8F9E97] hidden sm:inline" aria-hidden="true">•</span>
            <span className="text-[11px] text-[#71877D] font-medium">
              Guwahati–Tawang Safe Transit Corridor
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-[#193B32] font-semibold bg-[#F1F4E8] px-2.5 py-1 rounded-full border border-[#DCE5D8]">
            <span className="w-2 h-2 rounded-full bg-[#16A779] animate-pulse" aria-hidden="true" />
            <span>NER-LINK Dispatch Active (IST UTC +5:30)</span>
          </div>
        </div>

        {/* Tier 2: Driver Navigation Links + Copyright */}
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3 pt-0.5">
          <nav
            className="flex items-center flex-wrap gap-x-4 sm:gap-x-5 gap-y-1.5 text-xs font-semibold text-[#71877D]"
            aria-label="Driver quick navigation"
          >
            <Link
              href="/driver"
              className="hover:text-[#16A779] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-[#16A779] rounded"
            >
              Overview
            </Link>
            <span className="text-[#DCE5D8] hidden sm:inline" aria-hidden="true">/</span>
            <Link
              href="/driver/navigation"
              className="hover:text-[#16A779] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-[#16A779] rounded"
            >
              Active Trip
            </Link>
            <span className="text-[#DCE5D8] hidden sm:inline" aria-hidden="true">/</span>
            <Link
              href="/driver/report-incident"
              className="hover:text-[#16A779] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-[#16A779] rounded"
            >
              Report Incident
            </Link>
            <span className="text-[#DCE5D8] hidden sm:inline" aria-hidden="true">/</span>
            <Link
              href="/driver/trip-complete"
              className="hover:text-[#16A779] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-[#16A779] rounded"
            >
              Trip Log
            </Link>
            <span className="text-[#DCE5D8] hidden sm:inline" aria-hidden="true">/</span>
            <Link
              href="/map"
              className="hover:text-[#16A779] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-[#16A779] rounded"
            >
              Road Network Map
            </Link>
          </nav>

          <div className="text-[11px] text-[#8F9E97] whitespace-nowrap self-start lg:self-auto">
            © {CURRENT_YEAR} RouteX / NER-LINK · Road network data © OpenStreetMap
          </div>
        </div>
      </div>
    </footer>
  );
}
