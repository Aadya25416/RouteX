"use client";

import React, { useEffect, useRef, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import type { BackendInfoResponse, RoadFeatureCollection, RoadFeatureProperties } from "@/types/roads";

// Configure Web Worker URL for MapLibre in Next.js bundler
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

export interface VehicleMarkerData {
  id: string;
  lngLat: [number, number];
  label: string;
  speedKmh?: number | null;
  heading?: number | null;
  isCurrentDriver?: boolean;
  isStale?: boolean;
  updatedAt?: string;
}

export interface RoadMapProps {
  backendInfo?: BackendInfoResponse | null;
  roadsData?: RoadFeatureCollection | null;
  onSelectRoad?: (road: RoadFeatureProperties | null) => void;
  routeCoordinates?: [number, number][];
  hazardMarker?: {
    lngLat: [number, number];
    label: string;
    type?: string;
  } | null;
  stopMarkers?: {
    lngLat: [number, number];
    label: string;
    isDestination?: boolean;
    isNext?: boolean;
  }[];
  vehicleMarkers?: VehicleMarkerData[];
  customCenter?: [number, number];
  customZoom?: number;
  hideNavControls?: boolean;
  onMapClick?: (coords: [number, number]) => void;
  className?: string;
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

export default function RoadMap({
  backendInfo,
  roadsData,
  onSelectRoad,
  routeCoordinates,
  hazardMarker,
  stopMarkers,
  vehicleMarkers,
  customCenter,
  customZoom,
  hideNavControls,
  onMapClick,
  className,
}: RoadMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);
  const activePopupRef = useRef<maplibregl.Popup | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const vehicleMarkersMapRef = useRef<Map<string, { marker: maplibregl.Marker; el: HTMLDivElement }>>(new Map());
  const onSelectRoadRef = useRef(onSelectRoad);
  const onMapClickRef = useRef(onMapClick);

  useEffect(() => {
    onSelectRoadRef.current = onSelectRoad;
  }, [onSelectRoad]);

  useEffect(() => {
    onMapClickRef.current = onMapClick;
  }, [onMapClick]);

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
    const initialCenter: [number, number] = customCenter || [91.7362, 26.1445];
    const initialZoom = customZoom ?? 9;

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

    // Add navigation controls (zoom in/out, compass) if not hidden
    if (!hideNavControls) {
      map.addControl(new maplibregl.NavigationControl(), "top-right");
    }

    // Map click handler (for selecting location or coordinate inspect)
    map.on("click", (e) => {
      if (onMapClickRef.current) {
        onMapClickRef.current([e.lngLat.lng, e.lngLat.lat]);
      }
    });

    return () => {
      if (activePopupRef.current) {
        activePopupRef.current.remove();
      }
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      vehicleMarkersMapRef.current.forEach(({ marker }) => marker.remove());
      vehicleMarkersMapRef.current.clear();
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [customCenter, customZoom, hideNavControls]);

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
      addOrUpdateRoadSource(map, roadsData ?? null);
    } else {
      map.once("load", () => {
        addOrUpdateRoadSource(map, roadsData ?? null);
      });
    }
  }, [roadsData, addOrUpdateRoadSource]);

  // Handle optional route coordinates polyline
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !routeCoordinates || routeCoordinates.length < 2) return;

    const renderRoute = () => {
      const geojson: GeoJSON.Feature<GeoJSON.LineString> = {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: routeCoordinates,
        },
      };

      const existingSource = map.getSource("driver-route-source") as maplibregl.GeoJSONSource | undefined;
      if (existingSource) {
        existingSource.setData(geojson);
      } else {
        map.addSource("driver-route-source", {
          type: "geojson",
          data: geojson,
        });

        // Route casing for contrast
        map.addLayer({
          id: "driver-route-casing",
          type: "line",
          source: "driver-route-source",
          paint: {
            "line-color": "#0d3b2b",
            "line-width": 8,
            "line-opacity": 0.45,
          },
        });

        // Main vibrant green route line matching reference design
        map.addLayer({
          id: "driver-route-main",
          type: "line",
          source: "driver-route-source",
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          paint: {
            "line-color": "#16a779",
            "line-width": 5,
          },
        });
      }

      // Smoothly fit corridor to route
      const bounds = new maplibregl.LngLatBounds();
      routeCoordinates.forEach((coord) => bounds.extend(coord));
      map.fitBounds(bounds, { padding: 70, maxZoom: 12, duration: 800 });
    };

    if (map.isStyleLoaded()) {
      renderRoute();
    } else {
      map.once("load", renderRoute);
    }
  }, [routeCoordinates]);

  // Handle stop markers & hazard marker
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const attachMarkers = () => {
      // 1. Stop markers
      if (stopMarkers) {
        stopMarkers.forEach((stop) => {
          const isDest = Boolean(stop.isDestination);
          const borderColor = isDest ? "#ef4444" : "#16a779";
          const dotColor = isDest ? "#ef4444" : "#16a779";
          const textColor = isDest ? "#991b1b" : "#193b32";

          const el = document.createElement("div");
          el.className = "rx-map-stop-marker";
          el.style.cssText =
            `display: flex; align-items: center; gap: 6px; background: white; padding: 4px 8px; border-radius: 9999px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border: 1.5px solid ${borderColor}; font-size: 11px; font-weight: 700; color: ${textColor}; cursor: pointer; white-space: nowrap;`;

          const dot = document.createElement("span");
          dot.style.cssText = `width: 8px; height: 8px; border-radius: 50%; background: ${dotColor};`;
          el.appendChild(dot);

          const text = document.createElement("span");
          text.innerText = stop.label;
          el.appendChild(text);

          const marker = new maplibregl.Marker({ element: el })
            .setLngLat(stop.lngLat)
            .addTo(map);

          markersRef.current.push(marker);
        });
      }

      // 2. Hazard marker (e.g. ⚠️ Landslide Risk near Bomdila)
      if (hazardMarker) {
        const hEl = document.createElement("div");
        hEl.className = "rx-map-hazard-marker";
        hEl.style.cssText =
          "display: flex; align-items: center; gap: 5px; background: #FFF3E0; padding: 5px 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(230,81,0,0.25); border: 1.5px solid #F57C00; font-size: 11px; font-weight: 700; color: #E65100; cursor: pointer; white-space: nowrap;";

        const icon = document.createElement("span");
        icon.innerText = "⚠️";
        hEl.appendChild(icon);

        const text = document.createElement("span");
        text.innerText = hazardMarker.label;
        hEl.appendChild(text);

        const hMarker = new maplibregl.Marker({ element: hEl })
          .setLngLat(hazardMarker.lngLat)
          .addTo(map);

        markersRef.current.push(hMarker);
      }
    };

    if (map.isStyleLoaded()) {
      attachMarkers();
    } else {
      map.once("load", attachMarkers);
    }
  }, [stopMarkers, hazardMarker]);

  // Handle live vehicle markers with efficient position updates
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const updateVehicleMarkers = () => {
      const currentMap = vehicleMarkersMapRef.current;
      const nextIds = new Set((vehicleMarkers || []).map((v) => v.id));

      // Remove markers no longer in vehicleMarkers
      for (const [id, { marker }] of currentMap.entries()) {
        if (!nextIds.has(id)) {
          marker.remove();
          currentMap.delete(id);
        }
      }

      if (!vehicleMarkers || vehicleMarkers.length === 0) return;

      for (const v of vehicleMarkers) {
        const existing = currentMap.get(v.id);
        if (existing) {
          // Update position smoothly
          existing.marker.setLngLat(v.lngLat);
        } else {
          // Create marker element
          const isCurrent = Boolean(v.isCurrentDriver);
          const isStale = Boolean(v.isStale);

          const el = document.createElement("div");
          el.className = "rx-map-vehicle-marker";
          const bg = isCurrent ? "#059669" : isStale ? "#475569" : "#1e293b";
          const border = isCurrent ? "#34d399" : isStale ? "#94a3b8" : "#3b82f6";
          el.style.cssText = `display: flex; align-items: center; gap: 5px; background: ${bg}; color: #ffffff; padding: 4px 8px; border-radius: 9999px; border: 1.5px solid ${border}; box-shadow: 0 3px 10px rgba(0,0,0,0.25); font-size: 11px; font-weight: 700; cursor: pointer; white-space: nowrap; transition: transform 0.15s ease;`;

          const iconSpan = document.createElement("span");
          if (isCurrent) {
            iconSpan.innerHTML = `<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 0 2px rgba(52,211,153,0.4);"></span>`;
          } else if (isStale) {
            iconSpan.innerText = "⏳";
            iconSpan.style.fontSize = "10px";
          } else {
            iconSpan.innerText = "🚛";
            iconSpan.style.fontSize = "11px";
          }
          el.appendChild(iconSpan);

          const text = document.createElement("span");
          text.innerText = v.label;
          el.appendChild(text);

          if (v.speedKmh !== undefined && v.speedKmh !== null && !isStale) {
            const speedSpan = document.createElement("span");
            speedSpan.style.cssText = "font-size: 10px; opacity: 0.85; font-weight: 500;";
            speedSpan.innerText = `· ${Math.round(v.speedKmh)} km/h`;
            el.appendChild(speedSpan);
          }

          if (isStale) {
            const staleSpan = document.createElement("span");
            staleSpan.style.cssText = "font-size: 9px; opacity: 0.8; font-weight: 600; text-transform: uppercase;";
            staleSpan.innerText = "· STALE";
            el.appendChild(staleSpan);
          }

          // Popup on click
          const popupHtml = `
            <div style="font-family: inherit; font-size: 12px; line-height: 1.4; color: #111827; padding: 4px;">
              <div style="font-weight: 700; font-size: 13px; margin-bottom: 4px; color: ${bg};">
                ${isCurrent ? "📍 Your Vehicle" : "🚛 Fleet Vehicle"}: ${v.label}
              </div>
              <div><strong>Status:</strong> ${isStale ? "<span style='color: #d97706;'>Stale Location</span>" : "<span style='color: #059669;'>Live Tracking Active</span>"}</div>
              ${v.speedKmh !== undefined && v.speedKmh !== null ? `<div><strong>Speed:</strong> ${Math.round(v.speedKmh)} km/h</div>` : ""}
              <div><strong>Coordinates:</strong> ${v.lngLat[1].toFixed(5)}, ${v.lngLat[0].toFixed(5)}</div>
              ${v.updatedAt ? `<div style="font-size: 10px; color: #6b7280; margin-top: 4px;">Updated: ${new Date(v.updatedAt).toLocaleTimeString()}</div>` : ""}
            </div>
          `;
          const popup = new maplibregl.Popup({ offset: 12, maxWidth: "260px" }).setHTML(popupHtml);

          const marker = new maplibregl.Marker({ element: el })
            .setLngLat(v.lngLat)
            .setPopup(popup)
            .addTo(map);

          currentMap.set(v.id, { marker, el });
        }
      }
    };

    if (map.isStyleLoaded()) {
      updateVehicleMarkers();
    } else {
      map.once("load", updateVehicleMarkers);
    }
  }, [vehicleMarkers]);

  return (
    <div className={className || "relative w-full h-full min-h-[500px]"}>
      <div ref={mapContainerRef} className="w-full h-full absolute inset-0" />
    </div>
  );
}
