"use client";

import React, { useEffect, useState } from "react";

interface StatusItem {
  id: string;
  label: string;
  status: string;
  statusColor: string;
}

const ITEMS: StatusItem[] = [
  { id: "01", label: "Terrain layer", status: "ready", statusColor: "#8FCFC0" },
  { id: "02", label: "Road network", status: "awaiting backend", statusColor: "#F4B64A" },
  { id: "03", label: "Incident feed", status: "not connected", statusColor: "#4E877A" },
  { id: "04", label: "Route engine", status: "not connected", statusColor: "#4E877A" },
];

function getInitialCount(): number {
  if (typeof window === "undefined") return 0;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? ITEMS.length : 0;
}

export default function StatusLog() {
  const [visibleCount, setVisibleCount] = useState<number>(getInitialCount);

  useEffect(() => {
    if (visibleCount >= ITEMS.length) return;

    const timers: NodeJS.Timeout[] = [];
    ITEMS.forEach((_, idx) => {
      const timer = setTimeout(() => {
        setVisibleCount((prev) => Math.max(prev, idx + 1));
      }, 250 + idx * 300);
      timers.push(timer);
    });

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [visibleCount]);

  return (
    <div className="routex-status-log" aria-label="System Initialization Log">
      {ITEMS.map((item, idx) => {
        const isVisible = idx < visibleCount;
        return (
          <div
            key={item.id}
            className={`routex-status-row ${isVisible ? "routex-status-visible" : "routex-status-hidden"}`}
            style={{ transitionDelay: `${idx * 50}ms` }}
          >
            <span className="routex-status-id">{item.id}</span>
            <span className="routex-status-label">{item.label}</span>
            <span
              className="routex-status-val"
              style={{ color: item.statusColor }}
            >
              {item.status}
            </span>
          </div>
        );
      })}
    </div>
  );
}
