"use client";

import React from "react";
import Link from "next/link";

interface IncidentCardItem {
  id: string;
  title: string;
  description: string;
  href: string;
  iconBg: string;
  icon: React.ReactNode;
}

const INCIDENT_CARDS: IncidentCardItem[] = [
  {
    id: "landslide",
    title: "Report Landslide",
    description: "Fallen rocks or slope failure",
    href: "/driver/report-incident?type=landslide",
    iconBg: "#FFE4E6",
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#E11D48"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m8 3 4 8 5-5 5 15H2L8 3z" />
        <polygon points="12 11 17 6 22 21 12 21" fill="#E11D48" stroke="#E11D48" />
      </svg>
    ),
  },
  {
    id: "road_block",
    title: "Report Road Block",
    description: "Obstruction or closed road",
    href: "/driver/report-incident?type=road_block",
    iconBg: "#FFEDD5",
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#EA580C"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="2" y="6" width="20" height="8" rx="1" />
        <path d="M17 14v7" />
        <path d="M7 14v7" />
        <path d="M17 3v3" />
        <path d="M7 3v3" />
        <path d="M10 14 2.3 6.3" />
        <path d="m14 6 7.7 7.7" />
        <path d="m8 6 8 8" />
      </svg>
    ),
  },
  {
    id: "road_damage",
    title: "Report Road Damage",
    description: "Damaged road surface",
    href: "/driver/report-incident?type=weather",
    iconBg: "#FEF3C7",
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#D97706"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m9.3 6.2 1.4-2.8a2 2 0 0 1 2.6 0l1.4 2.8" />
        <path d="M6.3 15 8 11.5h8l1.7 3.5" />
        <path d="m4.3 19 1-2h13.4l1 2" />
        <path d="M3 20h18" />
      </svg>
    ),
  },
  {
    id: "other",
    title: "Report Other Issue",
    description: "Report any other problem",
    href: "/driver/report-incident?type=other",
    iconBg: "#E2E8F0",
    icon: (
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#334155"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
];

export default function QuickIncidentReporting() {
  return (
    <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline gap-1.5 sm:gap-3 mb-4">
        <h2 className="text-xl font-semibold text-[#193B32] tracking-tight">
          Report a Road Incident
        </h2>
        <p className="text-xs sm:text-sm text-[#71877D]">
          Help keep the corridor safe by reporting real-time issues
        </p>
      </div>

      {/* 4 Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {INCIDENT_CARDS.map((card) => (
          <Link
            key={card.id}
            href={card.href}
            className="bg-white border border-[#E5E7EB] rounded-2xl p-3.5 sm:p-4 flex items-center justify-between gap-3 hover:border-[#CBD5E1] hover:shadow-xs transition-all group cursor-pointer"
          >
            {/* Left part: Icon + (Title & Description) */}
            <div className="flex items-center gap-3.5 min-w-0">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                style={{ backgroundColor: card.iconBg }}
              >
                {card.icon}
              </div>

              <div className="flex flex-col min-w-0">
                <span className="text-[15px] font-bold text-[#193B32] leading-snug truncate">
                  {card.title}
                </span>
                <span className="text-xs text-[#71877D] leading-snug truncate mt-0.5">
                  {card.description}
                </span>
              </div>
            </div>

            {/* Right part: Circular Action Arrow */}
            <div className="w-9 h-9 rounded-full bg-[#EFF6FF] flex items-center justify-center shrink-0 text-[#1E3A5F] group-hover:bg-[#DBEAFE] group-hover:translate-x-0.5 transition-all">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#1E3A5F"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
