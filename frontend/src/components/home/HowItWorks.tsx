"use client";

import React from "react";

const STEPS = [
  {
    step: "01",
    title: "Observe",
    description: "Collect road-condition information and field reports across corridor checkpoints.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
    ),
  },
  {
    step: "02",
    title: "Verify",
    description: "Review incidents and determine which field reports and road closures are validated.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    ),
  },
  {
    step: "03",
    title: "Assess",
    description: "Understand affected road segments, hazard severity, and delivery implications.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
  },
  {
    step: "04",
    title: "Plan",
    description: "Use supported route recommendations and timing estimates to dispatch safely.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polygon points="12 2 19 21 12 17 5 21 12 2" />
      </svg>
    ),
  },
];

export default function HowItWorks() {
  return (
    <section className="home-section home-howitworks-section" id="how-it-works" aria-label="How It Works">
      <div className="home-section-container">
        {/* Header */}
        <div className="home-section-header">
          <div className="home-section-eyebrow">WORKFLOW OVERVIEW</div>
          <h2 className="home-section-title">From Road Conditions to Better Decisions</h2>
          <p className="home-section-desc">
            RouteX brings road intelligence and logistics workflows into one operational view.
          </p>
        </div>

        {/* 4-Step Sequence Grid */}
        <div className="howitworks-grid">
          {STEPS.map((item, idx) => (
            <div key={item.step} className="howitworks-card">
              <div className="howitworks-card-header">
                <span className="howitworks-step-num">{item.step}</span>
                <div className="howitworks-icon-circle">{item.icon}</div>
              </div>
              <h3 className="howitworks-card-title">{item.title}</h3>
              <p className="howitworks-card-desc">{item.description}</p>
              {idx < STEPS.length - 1 && (
                <div className="howitworks-connector" aria-hidden="true">→</div>
              )}
            </div>
          ))}
        </div>

        {/* Honest Operational Status Callout */}
        <div className="home-operational-notice">
          <span className="notice-icon">ℹ</span>
          <span>
            Phase 1 provides the read-only Road Map view for corridor segments. Incident validation and automated dispatch planning are in active staged development.
          </span>
        </div>
      </div>
    </section>
  );
}
