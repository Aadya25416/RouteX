"use client";

import React, { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

const LIGHT_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "background-fallback",
      type: "background",
      paint: {
        "background-color": "#EAF2E7",
      },
    },
    {
      id: "osm-tiles",
      type: "raster",
      source: "osm",
      paint: {
        "raster-saturation": -0.55,
        "raster-brightness-min": 0.5,
        "raster-brightness-max": 1.0,
        "raster-hue-rotate": 95,
        "raster-opacity": 1,
      },
    },
  ],
};

const ROUTES: maplibregl.GeoJSONSourceSpecification["data"] = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { kind: "main" },
      geometry: {
        type: "LineString",
        coordinates: [
          [91.748, 26.166],
          [92.1, 26.5],
          [92.6, 26.9],
          [92.9, 27.1],
          [92.6, 27.5],
          [92.2, 27.9],
          [91.866, 27.583],
        ],
      },
    },
    {
      type: "Feature",
      properties: { kind: "hazard" },
      geometry: {
        type: "LineString",
        coordinates: [[91.5, 26.05], [91.3, 25.9], [91.1, 25.75]],
      },
    },
    {
      type: "Feature",
      properties: { kind: "branch" },
      geometry: {
        type: "LineString",
        coordinates: [
          [92.9, 27.1],
          [93.5, 26.8],
          [94.1, 25.674],
        ],
      },
    },
    {
      type: "Feature",
      properties: { kind: "branch" },
      geometry: {
        type: "LineString",
        coordinates: [
          [94.1, 25.674],
          [94.0, 25.1],
          [93.936, 24.817],
        ],
      },
    },
  ],
};

const NODE_COORDS: [number, number][] = [
  [91.748, 26.166],
  [91.866, 27.583],
  [94.1, 25.674],
  [93.936, 24.817],
  [91.1, 25.75],
];

export default function LoginMapBackground() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || mapRef.current) return;

    const map = new maplibregl.Map({
      container: el,
      style: LIGHT_STYLE,
      center: [92.8, 26.4],
      zoom: 6.4,
      interactive: false,
      attributionControl: false,
      pitchWithRotate: false,
      dragRotate: false,
    });
    mapRef.current = map;

    const handleResize = () => {
      map.resize();
    };
    window.addEventListener("resize", handleResize);

    map.on("load", () => {
      map.resize();
      map.addSource("routes", { type: "geojson", data: ROUTES });
      map.addLayer({ id: "main-halo", type: "line", source: "routes", filter: ["==", ["get", "kind"], "main"], paint: { "line-color": "#16A779", "line-width": 10, "line-opacity": 0.22, "line-blur": 6 }, layout: { "line-cap": "round" } });
      map.addLayer({ id: "main-line", type: "line", source: "routes", filter: ["==", ["get", "kind"], "main"], paint: { "line-color": "#16A779", "line-width": 2.8, "line-opacity": 0.88 }, layout: { "line-cap": "round", "line-join": "round" } });
      map.addLayer({ id: "hazard-line", type: "line", source: "routes", filter: ["==", ["get", "kind"], "hazard"], paint: { "line-color": "#F4B64A", "line-width": 2.8, "line-opacity": 0.9 }, layout: { "line-cap": "round", "line-join": "round" } });
      map.addLayer({ id: "branch-line", type: "line", source: "routes", filter: ["==", ["get", "kind"], "branch"], paint: { "line-color": "#16A779", "line-width": 1.8, "line-opacity": 0.6, "line-dasharray": [4, 3] }, layout: { "line-cap": "round", "line-join": "round" } });

      const nodeGJ: maplibregl.GeoJSONSourceSpecification["data"] = {
        type: "FeatureCollection",
        features: NODE_COORDS.map(([lng, lat]) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [lng, lat] } })),
      };
      map.addSource("nodes", { type: "geojson", data: nodeGJ });
      map.addLayer({ id: "node-halo", type: "circle", source: "nodes", paint: { "circle-radius": 8, "circle-color": "rgba(22,167,121,0.18)" } });
      map.addLayer({ id: "node-dot", type: "circle", source: "nodes", paint: { "circle-radius": 4, "circle-color": "#16A779", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
    });

    return () => {
      window.removeEventListener("resize", handleResize);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div
      className="rx-login-map-bg"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        overflow: "hidden",
        pointerEvents: "none",
        backgroundColor: "#EAF2E7",
      }}
      aria-hidden="true"
    >
      <div
        ref={containerRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          backgroundColor: "#EAF2E7",
        }}
      />

      {/* SVG overlay: callout badges, labels, controls */}
      <svg
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Guwahati pin */}
        <g transform="translate(195,418)">
          <rect x="-46" y="-14" width="105" height="28" rx="14" fill="white" fillOpacity="0.93" stroke="#B5D9C4" strokeWidth="1"/>
          <circle cx="-31" cy="0" r="9" fill="#EAF2E7" stroke="#16A779" strokeWidth="1.5"/>
          <text x="-31" y="4" fontSize="10" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif">🚗</text>
          <text x="21" y="5" fontSize="12" fontWeight="700" fill="#0B3027" textAnchor="middle" fontFamily="system-ui,sans-serif">Guwahati</text>
        </g>

        {/* Place name labels */}
        <text x="220" y="162" fontSize="11" fill="#5A7A6A" fontFamily="system-ui,sans-serif" opacity="0.85">NAGAON</text>
        <text x="1238" y="100" fontSize="11" fill="#5A7A6A" fontFamily="system-ui,sans-serif" opacity="0.85">TAWANG</text>
        <text x="1268" y="290" fontSize="11" fill="#5A7A6A" fontFamily="system-ui,sans-serif" opacity="0.85">KOHIMA</text>
        <text x="1268" y="600" fontSize="11" fill="#5A7A6A" fontFamily="system-ui,sans-serif" opacity="0.85">IMPHAL</text>
        <text x="88" y="682" fontSize="11" fill="#5A7A6A" fontFamily="system-ui,sans-serif" opacity="0.85">HOJAI</text>

        {/* 6 hr 45 min */}
        <g transform="translate(1318,57)">
          <rect x="-55" y="-13" width="110" height="26" rx="13" fill="white" fillOpacity="0.93" stroke="#B5D9C4" strokeWidth="1"/>
          <text x="0" y="4.5" fontSize="11" fontWeight="700" fill="#0B3027" textAnchor="middle" fontFamily="system-ui,sans-serif">🚗 6 hr 45 min</text>
        </g>

        {/* 25 min */}
        <g transform="translate(1110,370)">
          <rect x="-36" y="-13" width="72" height="26" rx="13" fill="white" fillOpacity="0.93" stroke="#B5D9C4" strokeWidth="1"/>
          <text x="0" y="4.5" fontSize="11" fontWeight="700" fill="#0B3027" textAnchor="middle" fontFamily="system-ui,sans-serif">25 min</text>
        </g>

        {/* 3 hr 10 min */}
        <g transform="translate(1290,588)">
          <rect x="-55" y="-13" width="110" height="26" rx="13" fill="white" fillOpacity="0.93" stroke="#B5D9C4" strokeWidth="1"/>
          <text x="0" y="4.5" fontSize="11" fontWeight="700" fill="#0B3027" textAnchor="middle" fontFamily="system-ui,sans-serif">🚗 3 hr 10 min</text>
        </g>

        {/* Landslide Risk badge */}
        <g transform="translate(228,556)">
          <rect x="-64" y="-14" width="128" height="28" rx="14" fill="#FEF3C7" fillOpacity="0.97" stroke="#F4B64A" strokeWidth="1.4"/>
          <text x="0" y="5" fontSize="12" fontWeight="600" fill="#92400E" textAnchor="middle" fontFamily="system-ui,sans-serif">⚠ Landslide Risk</text>
        </g>

        {/* Compass */}
        <g transform="translate(68,820)">
          <circle cx="0" cy="0" r="24" fill="white" fillOpacity="0.9" stroke="#B5D9C4" strokeWidth="1"/>
          <text x="0" y="-9" fontSize="9" textAnchor="middle" fill="#174D3A" fontWeight="700" fontFamily="system-ui,sans-serif">N</text>
          <text x="0" y="15" fontSize="9" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif">S</text>
          <text x="-15" y="4" fontSize="9" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif">W</text>
          <text x="15" y="4" fontSize="9" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif">E</text>
          <polygon points="0,-15 3,-4 0,-8 -3,-4" fill="#16A779"/>
          <polygon points="0,15 3,4 0,8 -3,4" fill="#9DB5AA"/>
        </g>

        {/* Zoom + layer controls */}
        <g transform="translate(1404,460)">
          <rect x="-18" y="-54" width="36" height="36" rx="6" fill="white" fillOpacity="0.92" stroke="#D8E2D9" strokeWidth="1"/>
          <text x="0" y="-29" fontSize="18" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif" fontWeight="300">+</text>
          <rect x="-18" y="-14" width="36" height="36" rx="6" fill="white" fillOpacity="0.92" stroke="#D8E2D9" strokeWidth="1"/>
          <text x="0" y="11" fontSize="18" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif" fontWeight="300">−</text>
          <rect x="-18" y="26" width="36" height="36" rx="6" fill="white" fillOpacity="0.92" stroke="#D8E2D9" strokeWidth="1"/>
          <text x="0" y="51" fontSize="12" textAnchor="middle" fill="#174D3A" fontFamily="system-ui,sans-serif">⊞</text>
        </g>
      </svg>
    </div>
  );
}
