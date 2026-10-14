"use client";

import React, { useState, useEffect } from "react";
import "./LandingPage.css";
import TopographicCanvas from "./TopographicCanvas";
import HudFrame from "./HudFrame";
import RouteXTitle3D from "./RouteXTitle3D";
import GetStartedButton from "./GetStartedButton";
import ScrollToExplore from "./ScrollToExplore";

function getInitialTitleVisible(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function LandingPage() {
  const [titleVisible, setTitleVisible] = useState<boolean>(getInitialTitleVisible);
  const [coords, setCoords] = useState({ lat: "25.1148", lon: "91.1186" });

  useEffect(() => {
    if (titleVisible) return;

    // Title entrance initiates at ~1 second
    const timer = setTimeout(() => {
      setTitleVisible(true);
    }, 1000);

    return () => clearTimeout(timer);
  }, [titleVisible]);

  const handleCoordinateChange = (lat: string, lon: string) => {
    setCoords({ lat, lon });
  };

  return (
    <main className="routex-landing-root" role="main" aria-label="RouteX Mission Control">
      {/* 1. Topographic Canvas Background */}
      <TopographicCanvas onCoordinateChange={handleCoordinateChange} />

      {/* 2. HUD Frame, Status Log, Legends & Metadata */}
      <HudFrame currentLat={coords.lat} currentLon={coords.lon}>
        {/* 3. Central 3D Wordmark, Subtitle, and Get Started Button */}
        <div className="center-stage">
          <RouteXTitle3D visible={titleVisible} />
          <GetStartedButton revealDelayMs={3500} />
        </div>
      </HudFrame>

      {/* 4. Scroll To Explore Indicator */}
      <div className="scroll-area">
        <ScrollToExplore />
      </div>
    </main>
  );
}
