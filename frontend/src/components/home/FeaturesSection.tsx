"use client";

import React from "react";
import Link from "next/link";

const FEATURES = [
  {
    id: "road-intel",
    title: "Road Intelligence",
    description: "Understand road-segment status through a map-first operational interface.",
    statusBadge: "Phase 1 Live",
    badgeType: "live",
    linkText: "View Map →",
    href: "/map",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
        <line x1="8" y1="2" x2="8" y2="18" />
        <line x1="16" y1="6" x2="16" y2="22" />
      </svg>
    ),
  },
  {
    id: "incident-reporting",
    title: "Field Incident Reporting",
    description: "Support structured reporting of road disruptions with location and supporting evidence.",
    statusBadge: "Phase 2 Planned",
    badgeType: "planned",
    linkText: "Roadmap Details →",
    href: "#about",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    id: "risk-routing",
    title: "Risk-Aware Routing",
    description: "Present backend-calculated route alternatives and relevant disruption information when available.",
    statusBadge: "Phase 2 Planned",
    badgeType: "planned",
    linkText: "Roadmap Details →",
    href: "#about",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
  },
  {
    id: "logistics-visibility",
    title: "Logistics Visibility",
    description: "Bring trips, deliveries, and vehicle assignments into one operational workflow as integrations become available.",
    statusBadge: "Phase 3 Planned",
    badgeType: "planned",
    linkText: "Roadmap Details →",
    href: "#about",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="1" y="3" width="15" height="13" />
        <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
        <circle cx="5.5" cy="18.5" r="2.5" />
        <circle cx="18.5" cy="18.5" r="2.5" />
      </svg>
    ),
  },
];

export default function FeaturesSection() {
  return (
    <section className="home-section home-features-section" id="features" aria-label="Product Features">
      <div className="home-section-container">
        {/* Header */}
        <div className="home-section-header">
          <div className="home-section-eyebrow">CAPABILITIES</div>
          <h2 className="home-section-title">Built for Better Road Access</h2>
          <p className="home-section-desc">
            A connected workspace for road information, incident response, and logistics operations.
          </p>
        </div>

        {/* 4 Feature Cards Grid */}
        <div className="features-grid">
          {FEATURES.map((feat) => (
            <div key={feat.id} className="feature-card">
              <div className="feature-card-top">
                <div className="feature-card-icon">{feat.icon}</div>
                <span className={`feature-status-tag tag-${feat.badgeType}`}>
                  {feat.statusBadge}
                </span>
              </div>
              <h3 className="feature-card-title">{feat.title}</h3>
              <p className="feature-card-desc">{feat.description}</p>
              <div className="feature-card-footer">
                <Link href={feat.href} className="feature-card-link">
                  {feat.linkText}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
