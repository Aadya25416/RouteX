"use client";

import React from "react";
import Link from "next/link";

export default function AboutSection() {
  return (
    <section className="home-section home-about-section" id="about" aria-label="About RouteX">
      <div className="home-section-container">
        <div className="about-grid">
          {/* Left Column: Narrative */}
          <div className="about-left">
            <div className="home-section-eyebrow">ABOUT THE PLATFORM</div>
            <h2 className="home-section-title">Connecting Roads. Supporting Decisions.</h2>
            <p className="about-body-text">
              RouteX is designed to support road accessibility and logistics planning for difficult-to-access regions. By bringing road information, field observations, and transport workflows together, the platform aims to make disruptions easier to understand and operational decisions easier to coordinate.
            </p>
            <p className="about-body-text">
              The initial release targets the critical <strong>Guwahati–Tawang corridor</strong> in Northeast India, spanning high-altitude passes, monsoon-affected valleys, and remote administrative centers across Assam and Arunachal Pradesh.
            </p>
            <div className="about-cta-row">
              <Link href="/map" className="about-primary-btn">
                Launch Phase 1 Road Map →
              </Link>
            </div>
          </div>

          {/* Right Column: Architectural Highlights */}
          <div className="about-right">
            <div className="about-spec-box">
              <h3 className="spec-box-title">System Architecture</h3>
              <ul className="spec-list">
                <li className="spec-item">
                  <span className="spec-bullet">▪</span>
                  <div>
                    <strong>Road Network Foundation:</strong> Vectorized segments sourced from OpenStreetMap and local corridor surveys.
                  </div>
                </li>
                <li className="spec-item">
                  <span className="spec-bullet">▪</span>
                  <div>
                    <strong>MapLibre GL Client:</strong> High-performance client-side rendering with sub-second viewport filtering.
                  </div>
                </li>
                <li className="spec-item">
                  <span className="spec-bullet">▪</span>
                  <div>
                    <strong>FastAPI Backend Integration:</strong> Serving standardized GeoJSON geometries and status classifications.
                  </div>
                </li>
                <li className="spec-item">
                  <span className="spec-bullet">▪</span>
                  <div>
                    <strong>Extensible Incident Pipeline:</strong> Prepared for field reporter uploads, hazard verification, and weather ingestion.
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
