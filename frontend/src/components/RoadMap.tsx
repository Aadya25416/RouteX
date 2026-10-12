"use client";

import React, { useEffect, useRef, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";

// Configure Web Worker URL for MapLibre in Next.js bundler
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

interface RoadMapProps {
  backendInfo: BackendInfoResponse | null;
  roadsData: RoadFeatureCollection | null;
  onSelectRoad?: (road: RoadFeatureProperties | null) => void;
}

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: "osm-raster-layer",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

// Status badge styling helper
export function getStatusColor(status: string): string {
  switch (status) {
    case "OPEN":
      return "#10b981"; // green
    case "AT_RISK":
      return "#f59e0b"; // amber
    case "RESTRICTED":
      return "#f97316"; // orange
    case "BLOCKED":
      return "#ef4444"; // red
    case "UNKNOWN":
    default:
      return "#6b7280"; // neutral grey
  }
}

// Helper to smoothly fit bounds to corridor bbox
function fitCorridorBounds(
  map: maplibregl.Map,
  bbox: { south: number; west: number; north: number; east: number }
) {
  map.fitBounds(
    [
      [bbox.west, bbox.south],
      [bbox.east, bbox.north],
    ],
    {
      padding: 50,
      maxZoom: 14,
      duration: 1000,
    }
  );
}

export default function RoadMap({ backendInfo, roadsData, onSelectRoad }: RoadMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);
  const activePopupRef = useRef<maplibregl.Popup | null>(null);
  const onSelectRoadRef = useRef(onSelectRoad);

  useEffect(() => {
    onSelectRoadRef.current = onSelectRoad;
  }, [onSelectRoad]);

  const addOrUpdateRoadSource = useCallback((map: maplibregl.Map, data: RoadFeatureCollection | null) => {
    const emptyCollection: RoadFeatureCollection = {
      type: "FeatureCollection",
      features: [],
    };
    const geojsonData = data || emptyCollection;

    const existingSource = map.getSource("roads-source") as maplibregl.GeoJSONSource | undefined;

    if (existingSource) {
      existingSource.setData(geojsonData);
    } else {
      // Add source
      map.addSource("roads-source", {
        type: "geojson",
        data: geojsonData,
      });

      // Wide invisible line layer for easy click hit-testing
      map.addLayer({
        id: "roads-hit-target",
        type: "line",
        source: "roads-source",
        paint: {
          "line-width": 14,
          "line-opacity": 0,
        },
      });

      // Visual road layer styled by actual backend status
      map.addLayer({
        id: "roads-line-layer",
        type: "line",
        source: "roads-source",
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": [
            "match",
            ["get", "status"],
            "OPEN",
            "#10b981", // green
            "AT_RISK",
            "#f59e0b", // amber
            "RESTRICTED",
            "#f97316", // orange
            "BLOCKED",
            "#ef4444", // red
            /* fallback / UNKNOWN */
            "#6b7280", // neutral grey
          ],
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            7,
            2,
            11,
            3.5,
            15,
            6,
          ],
        },
      });

      // Mouse enter/leave cursor changes
      map.on("mouseenter", "roads-hit-target", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "roads-hit-target", () => {
        map.getCanvas().style.cursor = "";
      });

      // Click road segment for inspection popup
      map.on("click", "roads-hit-target", (e: maplibregl.MapLayerMouseEvent) => {
        if (!e.features || e.features.length === 0) return;

        const feature = e.features[0];
        const props = feature.properties as unknown as RoadFeatureProperties;

        if (onSelectRoadRef.current) {
          onSelectRoadRef.current(props);
        }

        const statusColor = getStatusColor(props.status);
        const isUnknown = props.status === "UNKNOWN";

        const disruptionText =
          props.disruption_probability != null && !isNaN(Number(props.disruption_probability))
            ? `${(Number(props.disruption_probability) * 100).toFixed(1)}%`
            : "Not evaluated";

        const safetyScoreText =
          props.safety_score != null && !isNaN(Number(props.safety_score))
            ? `${Number(props.safety_score).toFixed(1)} / 100`
            : "N/A";

        const lengthKm =
          props.length_m != null
            ? (Number(props.length_m) / 1000).toFixed(2)
            : "Unknown";

        const popupHtml = `
          <div style="font-family: inherit; font-size: 13px; min-width: 240px; color: #1f2937; line-height: 1.4;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
              <strong style="font-size: 14px; color: #111827;">${props.name || "Unnamed Road"}</strong>
              <span style="display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; color: white; background-color: ${statusColor};">
                ${props.status}
              </span>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 12px;">
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Canonical ID:</td>
                <td style="text-align: right; font-family: monospace; font-size: 11px; color: #374151;">${props.id}</td>
              </tr>
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Class:</td>
                <td style="text-align: right; text-transform: capitalize; color: #374151;">${props.road_class || "N/A"}</td>
              </tr>
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Length:</td>
                <td style="text-align: right; color: #374151;">${lengthKm} km (${Math.round(Number(props.length_m || 0))} m)</td>
              </tr>
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Traffic Direction:</td>
                <td style="text-align: right; color: #374151;">${props.oneway ? "One-way" : "Two-way"}</td>
              </tr>
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Safety Score:</td>
                <td style="text-align: right; font-weight: 600; color: #111827;">${safetyScoreText}</td>
              </tr>
              <tr>
                <td style="color: #6b7280; padding: 2px 0;">Disruption Probability:</td>
                <td style="text-align: right; font-weight: 600; color: #111827;">${disruptionText}</td>
              </tr>
            </table>

            ${
              isUnknown
                ? `
              <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 6px 8px; font-size: 11px; color: #991b1b;">
                ⚠️ <strong>UNKNOWN status:</strong> Operational status is unverified. Never assume safe or open.
              </div>
            `
                : ""
            }
          </div>
        `;

        if (activePopupRef.current) {
          activePopupRef.current.remove();
        }

        const popup = new maplibregl.Popup({ offset: 10, maxWidth: "320px" })
          .setLngLat(e.lngLat)
          .setHTML(popupHtml)
          .addTo(map);

        activePopupRef.current = popup;
      });
    }
  }, []);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Reinforce worker URL setup on client mount
    maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

    // Initial center fallback (Guwahati coordinates)
    const initialCenter: [number, number] = [91.7362, 26.1445];
    const initialZoom = 9;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: OSM_STYLE,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: {
        compact: false,
      },
    });

    mapInstanceRef.current = map;

    // Add navigation controls (zoom in/out, compass)
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    return () => {
      if (activePopupRef.current) {
        activePopupRef.current.remove();
      }
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Handle bounds update when backend info arrives
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !backendInfo?.corridor?.bbox) return;

    if (map.isStyleLoaded()) {
      fitCorridorBounds(map, backendInfo.corridor.bbox);
    } else {
      map.once("load", () => {
        if (backendInfo?.corridor?.bbox) {
          fitCorridorBounds(map, backendInfo.corridor.bbox);
        }
      });
    }
  }, [backendInfo]);

  // Handle roads data update
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (map.isStyleLoaded()) {
      addOrUpdateRoadSource(map, roadsData);
    } else {
      map.once("load", () => {
        addOrUpdateRoadSource(map, roadsData);
      });
    }
  }, [roadsData, addOrUpdateRoadSource]);

  return (
    <div className="relative w-full h-full min-h-[500px]">
      <div ref={mapContainerRef} className="w-full h-full absolute inset-0" />
    </div>
  );
}
