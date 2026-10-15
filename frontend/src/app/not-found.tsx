import React from "react";
import Link from "next/link";
import HomeFooter from "@/components/home/HomeFooter";

export default function NotFound() {
  return (
    <div className="flex flex-col min-h-screen bg-[#FAFBF7] text-[#193B32]">
      {/* Header */}
      <header className="px-6 py-4 border-b border-[#DCE5D8] bg-white flex items-center justify-between">
        <Link href="/home" className="flex items-center gap-1.5" aria-label="RouteX Home">
          <span className="text-xl font-black tracking-tight text-[#193B32]">
            Route<span className="text-[#16A779]">X</span>
          </span>
          <span className="text-[10px] font-bold uppercase bg-[#DDF4E8] text-[#12432A] px-2 py-0.5 rounded tracking-wide border border-[#B7E4CD]">
            Logistics
          </span>
        </Link>
        <Link
          href="/home"
          className="text-xs font-semibold text-[#71877D] hover:text-[#193B32] transition-colors"
        >
          Return to Home →
        </Link>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-lg mx-auto">
        <div className="w-16 h-16 rounded-3xl bg-[#DDF4E8] border border-[#B7E4CD] flex items-center justify-center text-2xl text-[#12432A] mb-4 shadow-xs">
          🧭
        </div>
        <span className="text-xs font-bold uppercase tracking-widest text-[#16A779] bg-[#DDF4E8] px-3 py-1 rounded-full border border-[#B7E4CD] mb-3">
          404 · Corridor Out of Range
        </span>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#193B32] mb-3 tracking-tight">
          Page Not Located
        </h1>
        <p className="text-sm text-[#71877D] mb-6 leading-relaxed">
          The requested corridor resource, document, or route does not exist or has been relocated. Check the URL or navigate via authorized platform portals.
        </p>

        <div className="flex items-center flex-wrap justify-center gap-3">
          <Link
            href="/home"
            className="px-5 py-2.5 rounded-full bg-[#12432A] text-white text-xs font-bold hover:bg-[#0d3420] transition-colors shadow-xs"
          >
            Corridor Home
          </Link>
          <Link
            href="/map"
            className="px-5 py-2.5 rounded-full bg-white border border-[#DCE5D8] text-[#193B32] text-xs font-bold hover:bg-[#F8FAF5] transition-colors shadow-xs"
          >
            Road Map
          </Link>
          <Link
            href="/login"
            className="px-5 py-2.5 rounded-full bg-white border border-[#DCE5D8] text-[#193B32] text-xs font-bold hover:bg-[#F8FAF5] transition-colors shadow-xs"
          >
            Staff Login
          </Link>
        </div>
      </main>

      {/* Standardized RouteX Global Footer */}
      <HomeFooter />
    </div>
  );
}
