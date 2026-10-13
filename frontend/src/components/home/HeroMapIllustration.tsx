"use client";

import React from "react";

export default function HeroMapIllustration() {
  return (
    <div className="hero-map-wrapper" aria-hidden="true">
      {/* ─── Topographic / Satellite Terrain Backdrop ───────────── */}
      <div className="hero-map-backdrop">
        {/* SVG Network Geometry */}
        <svg
          className="hero-map-svg"
          viewBox="0 0 1000 800"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="xMidYMid slice"
        >
          <defs>
            {/* Emerald Core Glow Filter */}
            <filter id="emerald-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Amber Hazard Glow Filter */}
            <filter id="amber-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Radial Terrain Gradient */}
            <radialGradient id="terrain-grad" cx="60%" cy="45%" r="65%">
              <stop offset="0%" stopColor="#0B382D" stopOpacity="0.85" />
              <stop offset="50%" stopColor="#06251E" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#031A15" stopOpacity="1" />
            </radialGradient>
          </defs>

          {/* Background Wash */}
          <rect width="1000" height="800" fill="url(#terrain-grad)" />

          {/* ─── Faint Topographic Contour Lines ────────────────── */}
          <g stroke="rgba(22, 167, 121, 0.08)" strokeWidth="1" fill="none">
            <path d="M 0 180 Q 250 140 500 210 T 1000 160" />
            <path d="M 0 260 Q 300 220 580 300 T 1000 240" />
            <path d="M 0 340 Q 220 300 480 370 T 1000 320" />
            <path d="M 0 420 Q 350 380 620 460 T 1000 400" />
            <path d="M 0 510 Q 280 470 540 550 T 1000 490" />
            <path d="M 0 600 Q 320 560 610 630 T 1000 580" />
            <path d="M 0 690 Q 240 660 520 720 T 1000 670" />
          </g>

          {/* ─── Secondary / Feeder Road Web ─────────────────────── */}
          <g stroke="rgba(143, 207, 192, 0.16)" strokeWidth="1" fill="none" strokeDasharray="3 4">
            <path d="M 120 420 L 260 380 L 380 320 L 520 280 L 640 220 L 780 180" />
            <path d="M 260 380 L 340 480 L 460 560 L 580 640" />
            <path d="M 520 280 L 590 360 L 680 410 L 760 360 L 840 270" />
            <path d="M 680 410 L 740 520 L 820 590" />
            <path d="M 380 320 L 440 240 L 540 180 L 700 140" />
            <path d="M 460 560 L 540 520 L 680 500 L 790 480" />
          </g>

          {/* Minor Feeder Nodes */}
          <g fill="rgba(143, 207, 192, 0.45)">
            <circle cx="340" cy="480" r="2.5" />
            <circle cx="440" cy="240" r="2.5" />
            <circle cx="540" cy="180" r="2.5" />
            <circle cx="640" cy="220" r="2.5" />
            <circle cx="760" cy="360" r="2.5" />
            <circle cx="740" cy="520" r="2.5" />
            <circle cx="820" cy="590" r="2.5" />
          </g>

          {/* ─── Primary Emerald Highway (Guwahati -> Tawang) ───── */}
          {/* Glow Layer */}
          <path
            d="M 220 380 Q 290 350 360 370 Q 430 390 490 340 Q 560 280 630 290 Q 710 300 780 230 Q 820 190 860 170"
            stroke="rgba(22, 167, 121, 0.45)"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
            filter="url(#emerald-glow)"
          />
          {/* Crisp Core Layer */}
          <path
            d="M 220 380 Q 290 350 360 370 Q 430 390 490 340 Q 560 280 630 290 Q 710 300 780 230 Q 820 190 860 170"
            stroke="#8FCFC0"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />

          {/* ─── Alternate Hazard Route (Fork to Imphal) ────────── */}
          {/* Amber Hazard Segment */}
          <path
            d="M 490 340 Q 520 400 550 440 Q 580 470 630 490"
            stroke="rgba(244, 182, 74, 0.5)"
            strokeWidth="6"
            strokeLinecap="round"
            fill="none"
            filter="url(#amber-glow)"
          />
          <path
            d="M 490 340 Q 520 400 550 440 Q 580 470 630 490"
            stroke="#F4B64A"
            strokeWidth="2.5"
            strokeLinecap="round"
            fill="none"
          />

          {/* Continuation from Hazard towards Imphal */}
          <path
            d="M 630 490 Q 670 510 710 560 Q 740 600 770 630"
            stroke="rgba(143, 207, 192, 0.5)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="5 5"
            fill="none"
          />

          {/* ─── State Watermark Labels ─────────────────────────── */}
          <g
            fill="rgba(143, 207, 192, 0.22)"
            fontSize="11"
            fontFamily="var(--font-geist-mono, monospace)"
            fontWeight="bold"
            letterSpacing="0.16em"
          >
            <text x="620" y="160">ARUNACHAL PRADESH</text>
            <text x="370" y="440">ASSAM</text>
            <text x="320" y="520">MEGHALAYA</text>
            <text x="420" y="620">TRIPURA</text>
            <text x="800" y="440">NAGALAND</text>
            <text x="790" y="520">MANIPUR</text>
            <text x="710" y="670">MIZORAM</text>
          </g>

          {/* ─── Hazard Markers (Small yellow warning triangles) ── */}
          <g fill="#F4B64A">
            {/* Triangle 1 near central fork */}
            <path d="M 545 330 L 551 341 L 539 341 Z" />
            {/* Triangle 2 near southern valley */}
            <path d="M 520 530 L 526 541 L 514 541 Z" />
            {/* Triangle 3 near eastern ridge */}
            <path d="M 690 310 L 696 321 L 684 321 Z" />
            {/* Triangle 4 south of Imphal */}
            <path d="M 605 610 L 611 621 L 599 621 Z" />
            {/* Triangle 5 near Kohima */}
            <path d="M 875 480 L 881 491 L 869 491 Z" />
          </g>

          {/* ─── Main Route Beacon Nodes ────────────────────────── */}
          {/* Guwahati Beacon */}
          <circle cx="220" cy="380" r="10" fill="rgba(22, 167, 121, 0.25)" />
          <circle cx="220" cy="380" r="5" fill="#16A779" stroke="#E4F3EA" strokeWidth="2" />

          {/* Central Junction Beacon */}
          <circle cx="490" cy="340" r="8" fill="rgba(22, 167, 121, 0.25)" />
          <circle cx="490" cy="340" r="4" fill="#8FCFC0" stroke="#06201A" strokeWidth="1.5" />

          {/* Hazard Fork Node (Pulsing Amber) */}
          <circle cx="550" cy="440" r="12" fill="rgba(244, 182, 74, 0.25)" />
          <circle cx="550" cy="440" r="5" fill="#F4B64A" stroke="#E4F3EA" strokeWidth="1.5" />

          {/* Tawang Endpoint Beacon */}
          <circle cx="860" cy="170" r="12" fill="rgba(22, 167, 121, 0.3)" />
          <circle cx="860" cy="170" r="6" fill="#16A779" stroke="#E4F3EA" strokeWidth="2.5" />

          {/* Imphal Endpoint Beacon */}
          <circle cx="710" cy="560" r="9" fill="rgba(143, 207, 192, 0.2)" />
          <circle cx="710" cy="560" r="4.5" fill="#8FCFC0" stroke="#06201A" strokeWidth="1.5" />

          {/* Kohima Node */}
          <circle cx="830" cy="270" r="4" fill="rgba(143, 207, 192, 0.6)" />
        </svg>

        {/* ─── Interactive / Styled HUD Overlays ────────────────── */}

        {/* 1. Guwahati Location Box */}
        <div className="map-badge-pin badge-guwahati">
          <span className="badge-text">Guwahati</span>
        </div>

        {/* 2. Tawang Location Box */}
        <div className="map-badge-pin badge-tawang">
          <span className="badge-text">Tawang</span>
        </div>

        {/* 3. Kohima Label */}
        <div className="map-text-pin badge-kohima">
          <span>Kohima</span>
        </div>

        {/* 4. Imphal Location Box */}
        <div className="map-badge-pin badge-imphal">
          <span className="badge-text">Imphal</span>
        </div>

        {/* 5. Travel Time 1: 25 min */}
        <div className="map-time-tag time-tag-1">
          <span className="time-icon">🚗</span>
          <span className="time-val">25 min</span>
        </div>

        {/* 6. Travel Time 2: 3 hr 10 min */}
        <div className="map-time-tag time-tag-2">
          <span className="time-icon">🚗</span>
          <span className="time-val">3 hr 10 min</span>
        </div>

        {/* 7. Landslide Risk Callout Badge */}
        <div className="map-hazard-badge">
          <span className="hazard-icon">⚠️</span>
          <span className="hazard-title">Landslide Risk</span>
        </div>

        {/* 8. Compass Rose Controls */}
        <div className="map-hud-compass">
          <div className="compass-circle">
            <span className="compass-n">N</span>
            <span className="compass-s">S</span>
            <span className="compass-w">W</span>
            <span className="compass-e">E</span>
            <div className="compass-needle" />
          </div>
        </div>

        {/* 9. Zoom & Layer Controls */}
        <div className="map-hud-controls">
          <button className="map-btn" aria-label="Zoom in" tabIndex={-1}>+</button>
          <button className="map-btn" aria-label="Zoom out" tabIndex={-1}>−</button>
          <button className="map-btn" aria-label="Layer options" tabIndex={-1}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          </button>
        </div>

        {/* Illustrative Data Tag */}
        <div className="map-illustrative-tag">
          ILLUSTRATIVE ROUTE DATA · DEMO
        </div>
      </div>
    </div>
  );
}
