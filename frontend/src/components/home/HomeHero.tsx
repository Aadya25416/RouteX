"use client";

import React from "react";
import Link from "next/link";
import HeroMapIllustration from "./HeroMapIllustration";

export default function HomeHero() {
  const handleScrollToHowItWorks = (e: React.MouseEvent) => {
    e.preventDefault();
    const target = document.getElementById("how-it-works");
    if (target) {
      target.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <section className="home-hero-section" id="overview" aria-label="Hero Overview">
      <div className="home-hero-container">
        {/* Left Column: Hero Editorial Content */}
        <div className="home-hero-left">
          {/* Eyebrow */}
          <div className="home-hero-eyebrow">
            SAFER ROUTES. STRONGER CONNECTIONS.
          </div>

          {/* Large Display Heading */}
          <h1 className="home-hero-title">
            <span className="title-line-1">Stronger</span>
            <span className="title-line-2">Connections</span>
          </h1>

          {/* Supporting Description */}
          <p className="home-hero-desc">
            AI-powered route intelligence for smarter logistics and safer journeys.
          </p>

          {/* CTA Row */}
          <div className="home-hero-cta-row">
            <Link href="/login" className="home-primary-cta" id="hero-explore-cta">
              <span className="cta-icon-circle" aria-hidden="true">→</span>
              <span className="cta-text">Explore RouteX →</span>
            </Link>

            <button
              type="button"
              onClick={handleScrollToHowItWorks}
              className="home-secondary-cta"
              id="hero-howitworks-cta"
            >
              <span className="play-icon-circle" aria-hidden="true">▶</span>
              <span className="secondary-text">How It Works</span>
            </button>
          </div>

          {/* Feature Highlights Row */}
          <div className="home-feature-highlights">
            {/* Highlight 1 */}
            <div className="feature-pill">
              <span className="feature-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
                  <line x1="8" y1="2" x2="8" y2="18" />
                  <line x1="16" y1="6" x2="16" y2="22" />
                </svg>
              </span>
              <span className="feature-label">Road Intelligence</span>
            </div>

            {/* Highlight 2 */}
            <div className="feature-pill">
              <span className="feature-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </span>
              <span className="feature-label">Risk-Aware Decisions</span>
            </div>

            {/* Highlight 3 */}
            <div className="feature-pill">
              <span className="feature-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
              </span>
              <span className="feature-label">Reliable Supply Chains</span>
            </div>
          </div>

          {/* Lower-Left Decorative Metric Card */}
          <div className="home-metric-card" aria-label="Route Coverage Metric">
            <div className="metric-header">
              <span className="metric-label">Route coverage (illustrative)</span>
            </div>
            <div className="metric-body">
              <span className="metric-number">~ 1,240 km</span>
              {/* Sparkline & Bars SVG */}
              <svg
                className="metric-sparkline-svg"
                viewBox="0 0 140 28"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                {/* Sine Trend Line */}
                <path
                  d="M0 24 Q 25 22 45 16 T 90 8 T 140 6"
                  stroke="#8FCFC0"
                  strokeWidth="1.8"
                  fill="none"
                />
                {/* Volume Activity Bars */}
                <rect x="40" y="20" width="2" height="6" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="48" y="18" width="2" height="8" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="56" y="16" width="2" height="10" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="64" y="14" width="2" height="12" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="72" y="12" width="2" height="14" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="80" y="15" width="2" height="11" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="88" y="10" width="2" height="16" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="96" y="13" width="2" height="13" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="104" y="9" width="2" height="17" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="112" y="7" width="2" height="19" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="120" y="11" width="2" height="15" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="128" y="8" width="2" height="18" fill="rgba(143, 207, 192, 0.4)" />
                <rect x="136" y="5" width="2" height="21" fill="rgba(143, 207, 192, 0.4)" />
              </svg>
            </div>
          </div>
        </div>

        {/* Right Column: Interactive Map Visualization */}
        <div className="home-hero-right">
          <HeroMapIllustration />
        </div>
      </div>
    </section>
  );
}
