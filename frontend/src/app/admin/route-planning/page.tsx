"use client";

import React, { useState, useEffect, useRef, useId } from "react";
import dynamic from "next/dynamic";
import AdminLayout from "@/components/admin/AdminLayout";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";
import type {
  RouteMode,
  RouteRecommendationResponse,
  Coordinates,
  LocationSuggestion,
} from "@/types/routing";

// Dynamically import RoadMap to avoid SSR issues with MapLibre
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[450px] bg-[#EAF2E7] flex items-center justify-center text-xs text-[#71877D]">
      Initializing MapLibre route planning engine...
    </div>
  ),
});

// Built-in known corridor hubs and landmarks across the Guwahati-Tawang study corridor
const CORRIDOR_SUGGESTIONS: LocationSuggestion[] = [
  { name: "Guwahati (Paltan Bazaar)", category: "Transit Hub", coords: { lat: 26.1856, lng: 91.7478 } },
  { name: "Dispur (Capital Complex)", category: "Administrative Hub", coords: { lat: 26.14365, lng: 91.74172 } },
  { name: "Guwahati Airport (Borjhar)", category: "Airport", coords: { lat: 26.1061, lng: 91.5859 } },
  { name: "Rangia (NH-27 Junction)", category: "Junction", coords: { lat: 26.4716, lng: 91.6212 } },
  { name: "Mangaldai (NH-15)", category: "Township", coords: { lat: 26.4385, lng: 92.0360 } },
  { name: "Nagaon (Central Junction)", category: "Transit Hub", coords: { lat: 26.3466, lng: 92.6840 } },
  { name: "Tezpur (Mission Chariali)", category: "Brahmaputra Crossing", coords: { lat: 26.6528, lng: 92.7926 } },
  { name: "Bhalukpong (Inner Line Checkpost)", category: "Border Checkpost", coords: { lat: 27.0142, lng: 92.6416 } },
  { name: "Bomdila (District HQ)", category: "Hill Station", coords: { lat: 27.2645, lng: 92.4225 } },
  { name: "Dirang Valley", category: "Valley Corridor", coords: { lat: 27.3598, lng: 92.2415 } },
  { name: "Sela Pass (Elevation 4,170m)", category: "High Mountain Pass", coords: { lat: 27.5042, lng: 92.1037 } },
  { name: "Tawang (Monastery / Town)", category: "Destination Hub", coords: { lat: 27.5861, lng: 91.8687 } },
  { name: "Hojai", category: "Rail Junction", coords: { lat: 26.0022, lng: 92.8592 } },
];

/** Helper to parse a "lat, lng" string */
function parseCoordinates(input: string): Coordinates | null {
  const trimmed = input.trim();
  const match = trimmed.match(/^([-+]?\d{1,2}(?:\.\d+)?)[,\s]+([-+]?\d{1,3}(?:\.\d+)?)$/);
  if (!match) return null;
  const lat = parseFloat(match[1]);
  const lng = parseFloat(match[2]);
  if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
    return { lat, lng };
  }
  return null;
}

/** Format seconds into "X hr Y min" */
function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "0 min";
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hrs > 0) {
    return mins > 0 ? `${hrs} hr ${mins} min` : `${hrs} hr`;
  }
  return `${mins} min`;
}

export default function RoutePlanningPage() {
  const fromInputId = useId();
  const toInputId = useId();

  // Location inputs and coordinates
  const [fromLocation, setFromLocation] = useState<string>("");
  const [fromCoord, setFromCoord] = useState<Coordinates | null>(null);
  const [toLocation, setToLocation] = useState<string>("");
  const [toCoord, setToCoord] = useState<Coordinates | null>(null);

  // Autocomplete UI state
  const [showFromSuggestions, setShowFromSuggestions] = useState<boolean>(false);
  const [showToSuggestions, setShowToSuggestions] = useState<boolean>(false);
  const fromSuggestionsRef = useRef<HTMLDivElement | null>(null);
  const toSuggestionsRef = useRef<HTMLDivElement | null>(null);

  // Map selection mode: "from" | "to" | null
  const [pickingMode, setPickingMode] = useState<"from" | "to" | null>(null);

  // Geolocation state
  const [isLocating, setIsLocating] = useState<boolean>(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  // Travel Mode: backend-supported modes
  const [travelMode, setTravelMode] = useState<RouteMode>("FASTEST_SAFE");
  const [requireVerifiedSafe, setRequireVerifiedSafe] = useState<boolean>(false);

  // Calculation & Results state
  const [isCalculating, setIsCalculating] = useState<boolean>(false);
  const [routeResult, setRouteResult] = useState<RouteRecommendationResponse | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Backend metadata and road graph
  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);

  useEffect(() => {
    fetch("/backend-api/info", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setBackendInfo(data))
      .catch(() => {});

    fetch("/api/v1/roads/geojson?limit=500", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setRoadsData(data))
      .catch(() => {});
  }, []);

  // Dismiss suggestion dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (fromSuggestionsRef.current && !fromSuggestionsRef.current.contains(e.target as Node)) {
        setShowFromSuggestions(false);
      }
      if (toSuggestionsRef.current && !toSuggestionsRef.current.contains(e.target as Node)) {
        setShowToSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter suggestions based on query
  const getFilteredSuggestions = (query: string): LocationSuggestion[] => {
    const q = query.trim().toLowerCase();
    if (!q) return CORRIDOR_SUGGESTIONS.slice(0, 6);
    return CORRIDOR_SUGGESTIONS.filter(
      (s) => s.name.toLowerCase().includes(q) || s.category?.toLowerCase().includes(q)
    );
  };

  // Handle typing in From field
  const handleFromChange = (value: string) => {
    setFromLocation(value);
    setValidationError(null);
    const parsed = parseCoordinates(value);
    if (parsed) {
      setFromCoord(parsed);
    } else {
      // Check exact name match
      const matched = CORRIDOR_SUGGESTIONS.find((s) => s.name.toLowerCase() === value.trim().toLowerCase());
      setFromCoord(matched ? matched.coords : null);
    }
  };

  // Handle typing in To field
  const handleToChange = (value: string) => {
    setToLocation(value);
    setValidationError(null);
    const parsed = parseCoordinates(value);
    if (parsed) {
      setToCoord(parsed);
    } else {
      const matched = CORRIDOR_SUGGESTIONS.find((s) => s.name.toLowerCase() === value.trim().toLowerCase());
      setToCoord(matched ? matched.coords : null);
    }
  };

  // Select a suggestion
  const handleSelectSuggestion = (field: "from" | "to", suggestion: LocationSuggestion) => {
    if (field === "from") {
      setFromLocation(suggestion.name);
      setFromCoord(suggestion.coords);
      setShowFromSuggestions(false);
    } else {
      setToLocation(suggestion.name);
      setToCoord(suggestion.coords);
      setShowToSuggestions(false);
    }
    setValidationError(null);
  };

  // Swap From and To
  const handleSwapLocations = () => {
    setFromLocation(toLocation);
    setFromCoord(toCoord);
    setToLocation(fromLocation);
    setToCoord(fromCoord);
    setValidationError(null);
  };

  // Clear a field
  const handleClearField = (field: "from" | "to") => {
    if (field === "from") {
      setFromLocation("");
      setFromCoord(null);
    } else {
      setToLocation("");
      setToCoord(null);
    }
    setValidationError(null);
  };

  // Map Click handler (used when in picking mode or clicking map)
  const handleMapClick = (coords: [number, number]) => {
    const [lng, lat] = coords;
    if (pickingMode === "from") {
      setFromCoord({ lat, lng });
      setFromLocation(`Selected Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
      setPickingMode(null);
      setValidationError(null);
    } else if (pickingMode === "to") {
      setToCoord({ lat, lng });
      setToLocation(`Selected Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
      setPickingMode(null);
      setValidationError(null);
    }
  };

  // Current Location via Geolocation API
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      setGeoError("Geolocation is not supported by your browser.");
      return;
    }
    setIsLocating(true);
    setGeoError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const { latitude, longitude } = pos.coords;
        setFromCoord({ lat: latitude, lng: longitude });
        setFromLocation(`Current Location (${latitude.toFixed(4)}, ${longitude.toFixed(4)})`);
        setValidationError(null);
      },
      (err) => {
        setIsLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError("Location access was denied. Please allow location permissions or select a point on the map.");
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setGeoError("Location information is currently unavailable.");
        } else if (err.code === err.TIMEOUT) {
          setGeoError("Location request timed out. Please try again or select on the map.");
        } else {
          setGeoError("Failed to obtain current location.");
        }
      },
      { timeout: 10000, maximumAge: 60000, enableHighAccuracy: true }
    );
  };

  // Execute Route Planning against backend
  const handlePlanRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setRouteError(null);

    // Resolve from coordinates
    let resolvedFrom = fromCoord;
    if (!resolvedFrom) {
      resolvedFrom = parseCoordinates(fromLocation);
      if (!resolvedFrom) {
        const found = CORRIDOR_SUGGESTIONS.find(
          (s) => s.name.toLowerCase() === fromLocation.trim().toLowerCase()
        );
        resolvedFrom = found?.coords ?? null;
      }
    }

    // Resolve to coordinates
    let resolvedTo = toCoord;
    if (!resolvedTo) {
      resolvedTo = parseCoordinates(toLocation);
      if (!resolvedTo) {
        const found = CORRIDOR_SUGGESTIONS.find(
          (s) => s.name.toLowerCase() === toLocation.trim().toLowerCase()
        );
        resolvedTo = found?.coords ?? null;
      }
    }

    if (!resolvedFrom) {
      setValidationError("Please select a starting point from suggestions, type coordinates (lat, lon), or pick on the map.");
      return;
    }
    if (!resolvedTo) {
      setValidationError("Please select a destination from suggestions, type coordinates (lat, lon), or pick on the map.");
      return;
    }

    setIsCalculating(true);
    setRouteResult(null);

    try {
      const response = await fetch("/api/v1/routes/plan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Role": "dispatcher",
          "X-User-Email": "dispatcher@nerlink.org",
        },
        body: JSON.stringify({
          origin_lat: resolvedFrom.lat,
          origin_lon: resolvedFrom.lng,
          destination_lat: resolvedTo.lat,
          destination_lon: resolvedTo.lng,
          mode: travelMode,
          require_verified_safe: requireVerifiedSafe,
          max_snapping_distance_m: 10000.0,
        }),
      });

      if (!response.ok) {
        let errorDetail = `Backend returned HTTP ${response.status} (${response.statusText})`;
        try {
          const errJson = await response.json();
          if (errJson.detail) {
            errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
          }
        } catch {
          // Keep default message
        }
        setRouteError(errorDetail);
        return;
      }

      const data: RouteRecommendationResponse = await response.json();
      setRouteResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error communicating with RouteX routing service.";
      setRouteError(`Failed to connect to backend: ${msg}`);
    } finally {
      setIsCalculating(false);
    }
  };

  // Assemble stop markers for the map
  const stopMarkers = [];
  if (fromCoord) {
    stopMarkers.push({
      lngLat: [fromCoord.lng, fromCoord.lat] as [number, number],
      label: fromLocation || "Start",
      isDestination: false,
    });
  }
  if (toCoord) {
    stopMarkers.push({
      lngLat: [toCoord.lng, toCoord.lat] as [number, number],
      label: toLocation || "Destination",
      isDestination: true,
    });
  }

  // Active route coordinates from genuine backend response
  const activeRouteCoords = routeResult?.route_geojson?.coordinates;

  return (
    <AdminLayout>
      <div className="flex flex-col gap-4 max-w-7xl mx-auto w-full">
        <div>
          <h1 className="text-xl font-extrabold text-[#193B32]">Route Planning</h1>
          <p className="text-xs text-[#71877D]">
            Calculate and evaluate optimal corridors considering active hazard constraints and directed road network topology
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Form & Alternatives (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* Input Form Card */}
            <form onSubmit={handlePlanRoute} className="rx-admin-card flex flex-col gap-3.5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-[#193B32]">Configure Route Parameters</h2>
                {fromLocation && toLocation && (
                  <button
                    type="button"
                    onClick={handleSwapLocations}
                    title="Swap Start and Destination"
                    className="text-xs text-[#16A779] hover:text-[#12432A] font-semibold flex items-center gap-1 cursor-pointer transition-colors"
                  >
                    <span>⇄</span> Swap
                  </button>
                )}
              </div>

              {/* Start Point (From) */}
              <div className="relative" ref={fromSuggestionsRef}>
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor={fromInputId} className="block text-xs font-bold text-[#71877D]">
                    From (Start Point)
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleUseCurrentLocation}
                      disabled={isLocating}
                      className="text-[11px] text-[#16A779] hover:underline font-semibold flex items-center gap-0.5 cursor-pointer disabled:opacity-50"
                    >
                      {isLocating ? "Locating..." : "📍 My Location"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPickingMode(pickingMode === "from" ? null : "from")}
                      className={`text-[11px] px-2 py-0.5 rounded font-semibold cursor-pointer transition-colors ${
                        pickingMode === "from"
                          ? "bg-[#ef4444] text-white"
                          : "bg-[#DDF4E8] text-[#12432A] hover:bg-[#c6edd8]"
                      }`}
                    >
                      {pickingMode === "from" ? "✕ Cancel Pick" : "📍 Pick on Map"}
                    </button>
                  </div>
                </div>

                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs">🟢</span>
                  <input
                    id={fromInputId}
                    type="text"
                    value={fromLocation}
                    onChange={(e) => handleFromChange(e.target.value)}
                    onFocus={() => setShowFromSuggestions(true)}
                    placeholder="Type hub name or lat, lng..."
                    className="w-full pl-8 pr-8 py-2 text-xs bg-white border border-[#DCE5D8] rounded-xl font-semibold text-[#193B32] outline-none focus:border-[#16A779]"
                  />
                  {fromLocation && (
                    <button
                      type="button"
                      onClick={() => handleClearField("from")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-[#9CA3AF] hover:text-[#4B5563]"
                      title="Clear"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {fromCoord && (
                  <div className="text-[10px] text-[#16A779] font-medium mt-0.5 pl-1">
                    Coordinates: {fromCoord.lat.toFixed(5)}, {fromCoord.lng.toFixed(5)}
                  </div>
                )}

                {/* Suggestions Dropdown */}
                {showFromSuggestions && (
                  <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-[#DCE5D8] rounded-xl shadow-lg z-30 max-h-48 overflow-y-auto">
                    {getFilteredSuggestions(fromLocation).map((sug) => (
                      <button
                        key={sug.name}
                        type="button"
                        onClick={() => handleSelectSuggestion("from", sug)}
                        className="w-full px-3 py-2 text-left text-xs hover:bg-[#FAFBF7] flex items-center justify-between border-b border-[#F0F2EB] last:border-b-0 cursor-pointer"
                      >
                        <span className="font-semibold text-[#193B32]">{sug.name}</span>
                        {sug.category && (
                          <span className="text-[10px] text-[#71877D] bg-[#F0F4EE] px-1.5 py-0.5 rounded">
                            {sug.category}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Destination Point (To) */}
              <div className="relative" ref={toSuggestionsRef}>
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor={toInputId} className="block text-xs font-bold text-[#71877D]">
                    To (Destination)
                  </label>
                  <button
                    type="button"
                    onClick={() => setPickingMode(pickingMode === "to" ? null : "to")}
                    className={`text-[11px] px-2 py-0.5 rounded font-semibold cursor-pointer transition-colors ${
                      pickingMode === "to"
                        ? "bg-[#ef4444] text-white"
                        : "bg-[#DDF4E8] text-[#12432A] hover:bg-[#c6edd8]"
                    }`}
                  >
                    {pickingMode === "to" ? "✕ Cancel Pick" : "🏁 Pick on Map"}
                  </button>
                </div>

                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs">🔴</span>
                  <input
                    id={toInputId}
                    type="text"
                    value={toLocation}
                    onChange={(e) => handleToChange(e.target.value)}
                    onFocus={() => setShowToSuggestions(true)}
                    placeholder="Type destination or lat, lng..."
                    className="w-full pl-8 pr-8 py-2 text-xs bg-white border border-[#DCE5D8] rounded-xl font-semibold text-[#193B32] outline-none focus:border-[#16A779]"
                  />
                  {toLocation && (
                    <button
                      type="button"
                      onClick={() => handleClearField("to")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-[#9CA3AF] hover:text-[#4B5563]"
                      title="Clear"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {toCoord && (
                  <div className="text-[10px] text-[#16A779] font-medium mt-0.5 pl-1">
                    Coordinates: {toCoord.lat.toFixed(5)}, {toCoord.lng.toFixed(5)}
                  </div>
                )}

                {/* Suggestions Dropdown */}
                {showToSuggestions && (
                  <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-[#DCE5D8] rounded-xl shadow-lg z-30 max-h-48 overflow-y-auto">
                    {getFilteredSuggestions(toLocation).map((sug) => (
                      <button
                        key={sug.name}
                        type="button"
                        onClick={() => handleSelectSuggestion("to", sug)}
                        className="w-full px-3 py-2 text-left text-xs hover:bg-[#FAFBF7] flex items-center justify-between border-b border-[#F0F2EB] last:border-b-0 cursor-pointer"
                      >
                        <span className="font-semibold text-[#193B32]">{sug.name}</span>
                        {sug.category && (
                          <span className="text-[10px] text-[#71877D] bg-[#F0F4EE] px-1.5 py-0.5 rounded">
                            {sug.category}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Geo Error notification */}
              {geoError && (
                <div className="p-2.5 rounded-lg bg-[#FEF2F2] border border-[#FECACA] text-[11px] text-[#991B1B]">
                  {geoError}
                </div>
              )}

              {/* Supported Route Optimization Modes */}
              <div>
                <label className="block text-xs font-bold text-[#71877D] mb-1.5">
                  Optimization Mode (Backend Algorithm)
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setTravelMode("FASTEST_SAFE")}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold flex flex-col items-start gap-0.5 transition-all cursor-pointer ${
                      travelMode === "FASTEST_SAFE"
                        ? "bg-[#DDF4E8] border-[#16A779] text-[#12432A]"
                        : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D]"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span>🛡️</span> Fastest Safe
                    </span>
                    <span className="text-[10px] font-normal opacity-80">
                      Applies risk multipliers, bypasses confirmed blockages
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setTravelMode("SHORTEST_DISTANCE")}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold flex flex-col items-start gap-0.5 transition-all cursor-pointer ${
                      travelMode === "SHORTEST_DISTANCE"
                        ? "bg-[#DDF4E8] border-[#16A779] text-[#12432A]"
                        : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D]"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span>📏</span> Shortest Distance
                    </span>
                    <span className="text-[10px] font-normal opacity-80">
                      Minimizes physical distance on open road graph
                    </span>
                  </button>
                </div>
              </div>

              {/* Require verified safe policy toggle */}
              <label className="flex items-center gap-2 text-xs text-[#193B32] font-medium cursor-pointer">
                <input
                  type="checkbox"
                  checked={requireVerifiedSafe}
                  onChange={(e) => setRequireVerifiedSafe(e.target.checked)}
                  className="rounded border-[#DCE5D8] text-[#16A779] focus:ring-[#16A779]"
                />
                <span>Strict Safety Policy (Reject UNKNOWN / unverified road states)</span>
              </label>

              {/* Validation error */}
              {validationError && (
                <div className="p-2.5 rounded-lg bg-[#FEF2F2] border border-[#FECACA] text-[11px] text-[#991B1B]">
                  {validationError}
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={isCalculating}
                className="w-full py-2.5 mt-1 bg-[#12432A] hover:bg-[#0b2f1c] text-white rounded-full text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
              >
                {isCalculating ? (
                  <span>Evaluating Road Safety &amp; Topology...</span>
                ) : (
                  <>
                    <span>Find Best Route</span>
                    <span>→</span>
                  </>
                )}
              </button>
            </form>

            {/* Route Results Section */}
            <div className="space-y-2.5">
              <h2 className="text-xs font-bold text-[#71877D] uppercase tracking-wider">
                Route Results
              </h2>

              {/* Empty state before search */}
              {!isCalculating && !routeResult && !routeError && (
                <div className="rx-admin-card p-6 text-center flex flex-col items-center justify-center gap-2 bg-[#FAFBF7] border border-[#DCE5D8]">
                  <span className="text-2xl">🗺️</span>
                  <p className="text-xs font-semibold text-[#193B32]">
                    Choose a starting point and destination to find available routes.
                  </p>
                  <p className="text-[11px] text-[#71877D] max-w-xs">
                    Type a location name, enter coordinates, or click &ldquo;Pick on Map&rdquo; to set origin and destination points.
                  </p>
                </div>
              )}

              {/* Calculating loading state */}
              {isCalculating && (
                <div className="rx-admin-card p-6 text-center flex flex-col items-center justify-center gap-2 bg-white border border-[#16A779]">
                  <div className="w-5 h-5 border-2 border-[#16A779] border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs font-bold text-[#193B32]">
                    Evaluating road network &amp; active hazard constraints...
                  </p>
                  <p className="text-[11px] text-[#71877D]">
                    Snapping coordinates to nearest PostGIS road nodes and running directed path search.
                  </p>
                </div>
              )}

              {/* Error or No Route state */}
              {routeError && (
                <div className="rx-admin-card p-4 bg-[#FEF2F2] border border-[#FECACA] flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#991B1B]">
                    <span>⚠️</span>
                    <span>Route Planning Notice</span>
                  </div>
                  <p className="text-xs text-[#7F1D1D]">{routeError}</p>
                  <div className="text-[11px] text-[#991B1B] bg-white/60 p-2.5 rounded-lg border border-[#FCA5A5]/40 flex flex-col gap-1">
                    <span className="font-semibold">Troubleshooting:</span>
                    <span>• Ensure the FastAPI backend is running at <code className="bg-[#FEE2E2] px-1 py-0.5 rounded">http://127.0.0.1:8000</code>.</span>
                    <span>• Ensure OSM road network nodes have been ingested into PostGIS via <code className="bg-[#FEE2E2] px-1 py-0.5 rounded">uv run python -m backend.scripts.import_osm</code>.</span>
                    <span>• Verify that start and destination points fall within 10km of routable road segments.</span>
                  </div>
                </div>
              )}

              {/* Genuine Backend Route Result Card */}
              {routeResult && (
                <div className="rx-admin-card p-4 border-2 border-[#16A779] bg-white shadow-md flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#193B32]">
                      {routeResult.mode === "FASTEST_SAFE" ? "Recommended: Fastest Safe Corridor" : "Optimal: Shortest Distance Route"}
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      routeResult.safety_summary.safety_status === "VERIFIED_SAFE"
                        ? "bg-[#DDF4E8] text-[#12432A]"
                        : routeResult.safety_summary.safety_status === "AT_RISK"
                        ? "bg-[#FEF3C7] text-[#92400E]"
                        : routeResult.safety_summary.safety_status === "RESTRICTED"
                        ? "bg-[#FFEDD5] text-[#9A3412]"
                        : "bg-[#F3F4F6] text-[#374151]"
                    }`}>
                      {routeResult.safety_summary.safety_status}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs font-bold text-[#193B32]">
                    <span>{(routeResult.distance_m / 1000).toFixed(1)} km</span>
                    <span className="text-[#71877D] font-normal">•</span>
                    <span>{formatDuration(routeResult.eta_seconds)}</span>
                    <span className="text-[#71877D] font-normal">•</span>
                    <span className="text-[#16A779]">
                      {routeResult.ordered_segment_ids.length} road segments
                    </span>
                  </div>

                  {/* Safety Summary Breakdown */}
                  <div className="grid grid-cols-2 gap-2 text-[11px] bg-[#FAFBF7] p-2.5 rounded-lg border border-[#DCE5D8]">
                    <div>
                      <span className="text-[#71877D]">Blocked Segments: </span>
                      <span className="font-bold text-[#193B32]">{routeResult.safety_summary.blocked_segment_count}</span>
                    </div>
                    <div>
                      <span className="text-[#71877D]">Restricted: </span>
                      <span className="font-bold text-[#193B32]">{routeResult.safety_summary.restricted_segment_count}</span>
                    </div>
                    <div>
                      <span className="text-[#71877D]">At Risk: </span>
                      <span className="font-bold text-[#193B32]">{routeResult.safety_summary.at_risk_segment_count}</span>
                    </div>
                    <div>
                      <span className="text-[#71877D]">Unknown / Unverified: </span>
                      <span className="font-bold text-[#193B32]">{routeResult.safety_summary.unknown_segment_count}</span>
                    </div>
                  </div>

                  {routeResult.avoided_hazard_count > 0 && (
                    <p className="text-[11px] text-[#0D6E4E] font-medium">
                      🛡️ Successfully routed around {routeResult.avoided_hazard_count} active hazard disruptions.
                    </p>
                  )}

                  {routeResult.safety_summary.disclaimer && (
                    <p className="text-[10px] text-[#71877D] italic border-t border-[#F0F2EB] pt-2">
                      Notice: {routeResult.safety_summary.disclaimer}
                    </p>
                  )}

                  {/* Snapped Points Telemetry */}
                  <div className="text-[10px] text-[#71877D] border-t border-[#F0F2EB] pt-2 flex flex-col gap-0.5">
                    <span>Origin snapped to node: <code className="font-mono text-[#193B32]">{routeResult.snapped_origin.node_id}</code> ({routeResult.snapped_origin.distance_m.toFixed(1)}m offset)</span>
                    <span>Destination snapped to node: <code className="font-mono text-[#193B32]">{routeResult.snapped_destination.node_id}</code> ({routeResult.snapped_destination.distance_m.toFixed(1)}m offset)</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Map Display (7 cols) */}
          <div className="lg:col-span-7 rx-admin-card p-0 overflow-hidden relative min-h-[520px] h-[580px] bg-[#EAF2E7]">
            {/* Active Map-Picking Notification Bar */}
            {pickingMode && (
              <div className="absolute top-3 left-3 right-3 z-20 bg-[#12432A] text-white px-4 py-2.5 rounded-xl shadow-lg flex items-center justify-between border border-[#16A779]">
                <div className="flex items-center gap-2 text-xs font-bold">
                  <span className="animate-pulse text-base">📍</span>
                  <span>
                    {pickingMode === "from"
                      ? "Map Selection Active: Click anywhere on the map to set Start Point"
                      : "Map Selection Active: Click anywhere on the map to set Destination"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setPickingMode(null)}
                  className="px-2.5 py-1 bg-white/20 hover:bg-white/30 rounded-lg text-xs font-bold cursor-pointer transition-colors"
                >
                  Cancel Selection
                </button>
              </div>
            )}

            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              routeCoordinates={activeRouteCoords}
              stopMarkers={stopMarkers}
              onMapClick={handleMapClick}
              customCenter={[92.2, 26.9]}
              customZoom={7.6}
              className={`w-full h-full relative ${pickingMode ? "cursor-crosshair" : ""}`}
            />

            {/* Floating Route Info Badge when route is active */}
            {routeResult && (
              <div className="absolute bottom-4 left-4 z-10 bg-white/95 backdrop-blur-md px-4 py-2.5 rounded-xl shadow-lg border border-[#DCE5D8] flex items-center gap-3">
                <span className="text-xl">🛣️</span>
                <div>
                  <span className="text-xs font-extrabold text-[#193B32] block">
                    {formatDuration(routeResult.eta_seconds)} ({(routeResult.distance_m / 1000).toFixed(1)} km)
                  </span>
                  <span className="text-[10px] text-[#71877D]">
                    {fromLocation || "Start"} → {toLocation || "Destination"} • {routeResult.mode === "FASTEST_SAFE" ? "Fastest Safe" : "Shortest Distance"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
