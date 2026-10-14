"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import StatusLog from "./StatusLog";

interface HudFrameProps {
  currentLat?: string;
  currentLon?: string;
  children?: React.ReactNode;
}

const LEGEND_ITEMS = [
  { label: "Open", color: "#16A779" },
  { label: "At risk", color: "#F4B64A" },
  { label: "Restricted", color: "#F07838" },
  { label: "Blocked", color: "#DC4848" },
  { label: "Unknown", color: "#89939A" },
];

export default function HudFrame({
  currentLat = "25.1148",
  currentLon = "91.1186",
  children,
}: HudFrameProps) {
  const [timeStr, setTimeStr] = useState<string>("21:27:45 IST");

  useEffect(() => {
    function updateClock() {
      const now = new Date();
      const formatted = now.toLocaleTimeString("en-GB", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      setTimeStr(`${formatted} IST`);
    }

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="routex-hud-frame" aria-label="HUD Mission Control Interface">
      {/* ─── Corner Markers ────────────────────────────────────── */}
      <div className="hud-corner hud-corner-tl" aria-hidden="true">+</div>
      <div className="hud-corner hud-corner-tr" aria-hidden="true">+</div>
      <div className="hud-corner hud-corner-bl" aria-hidden="true">+</div>
      <div className="hud-corner hud-corner-br" aria-hidden="true">+</div>

      {/* ─── Top Left: Metadata & Status Log ───────────────────── */}
      <header className="hud-section hud-top-left">
        <div className="hud-meta-block">
          <div className="hud-brand-title">NER-LINK / ROAD-ACCESS</div>
          <div className="hud-meta-line">
            <span className="hud-meta-key">CORRIDOR</span>
            <span className="hud-meta-val">Guwahati - Tawang</span>
          </div>
          <div className="hud-meta-line">
            <span className="hud-meta-key">LOCAL TIME</span>
            <span className="hud-meta-val">{timeStr}</span>
          </div>
        </div>

        <StatusLog />
      </header>

      {/* ─── Top Center: Branded Watermark ─────────────────────── */}
      <div className="hud-section hud-top-center" aria-hidden="true">
        <span className="hud-watermark">ROUTEX</span>
      </div>

      {/* ─── Top Right: Navigation & Status Legend ─────────────── */}
      <div className="hud-section hud-top-right">
        <div className="hud-auth-row">
          <Link href="/login" className="hud-signin-link" id="hud-signin-link">
            Sign in
          </Link>
        </div>
        <div className="hud-phase-label">Phase 1 · read-only map</div>

        <div className="hud-legend" aria-label="Road Status Legend">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.label} className="hud-legend-item">
              <span className="hud-legend-text">{item.label}</span>
              <span
                className="hud-legend-bar"
                style={{ backgroundColor: item.color }}
                aria-hidden="true"
              />
            </div>
          ))}
        </div>
      </div>

      {/* ─── Main Content Slot (RouteX title, subtext, button) ─── */}
      {children}

      {/* ─── Bottom Left: Segments in View Counter ─────────────── */}
      <div className="hud-section hud-bottom-left">
        <div className="hud-counter-label">
          Segments in view <span className="hud-label-dim">· demo fixture</span>
        </div>
        <div className="hud-counter-number">001.284</div>
      </div>

      {/* ─── Bottom Center: Coordinates Readout ───────────────── */}
      <div className="hud-section hud-bottom-center">
        <div className="hud-coord-readout" aria-live="off">
          LAT {currentLat} N LON {currentLon} E
        </div>
      </div>

      {/* ─── Bottom Right: Reports Sparkline ───────────────────── */}
      <div className="hud-section hud-bottom-right">
        <div className="hud-sparkline-label">
          Reports per day <span className="hud-label-dim">· demo</span>
        </div>
        <svg
          className="hud-sparkline-svg"
          viewBox="0 0 160 20"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M0 12 L15 12 L25 15 L35 8 L45 13 L55 9 L65 14 L75 11 L85 15 L95 7 L105 13 L115 10 L125 14 L135 9 L145 13 L160 12"
            stroke="#8FCFC0"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}
