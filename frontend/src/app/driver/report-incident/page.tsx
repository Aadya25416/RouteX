"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import DriverLayout from "@/components/driver/DriverLayout";
import { DriverIncidentType } from "@/types/driver";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { searchLocations, reverseGeocodeCoordinates, GeocodeSuggestion } from "@/lib/geocoding";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

// Dynamically import RoadMap
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[350px] bg-[#EAF2E7] flex items-center justify-center text-sm text-[#71877D]">
      Initializing MapLibre hazard locator...
    </div>
  ),
});

// Vector icons matching the reference design for incident selection
function IconLandslide() {
  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0"
      aria-hidden="true"
    >
      {/* Mountain Body with Emerald and Forest Green Facets */}
      <polygon points="14,6 4,28 20,28" fill="#10B981" />
      <polygon points="14,6 9,28 4,28" fill="#0D6838" />
      <polygon points="14,6 17,28 20,28" fill="#047857" />
      <polygon points="14,6 12,28 17,28" fill="#059669" />
      {/* Falling rocks tumbling down the right slope */}
      <circle cx="23" cy="14" r="2" fill="#0D6838" />
      <circle cx="25.5" cy="20" r="2.3" fill="#0D6838" />
      <circle cx="28" cy="26" r="2.7" fill="#0D6838" />
      <circle cx="22" cy="25" r="1.5" fill="#10B981" />
    </svg>
  );
}

function IconRoadBlock() {
  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0"
      aria-hidden="true"
    >
      {/* Top circular caps/reflectors */}
      <circle cx="9" cy="7.5" r="2.2" fill="#F97316" stroke="#334155" strokeWidth="1.2" />
      <circle cx="27" cy="7.5" r="2.2" fill="#F97316" stroke="#334155" strokeWidth="1.2" />
      {/* Vertical steel posts */}
      <rect x="8" y="9" width="2" height="18" rx="1" fill="#475569" />
      <rect x="26" y="9" width="2" height="18" rx="1" fill="#475569" />
      {/* Feet / bases */}
      <rect x="6" y="27" width="6" height="2" rx="1" fill="#334155" />
      <rect x="24" y="27" width="6" height="2" rx="1" fill="#334155" />
      {/* Striped barricade board */}
      <g>
        <defs>
          <clipPath id="rb-stripes-clip">
            <rect x="4" y="12" width="28" height="10" rx="1.5" />
          </clipPath>
        </defs>
        <rect x="4" y="12" width="28" height="10" rx="1.5" fill="#EA580C" />
        <g clipPath="url(#rb-stripes-clip)">
          <path d="M2 24 L10 10 L14 10 L6 24 Z" fill="#FFFFFF" />
          <path d="M11 24 L19 10 L23 10 L15 24 Z" fill="#FFFFFF" />
          <path d="M20 24 L28 10 L32 10 L24 24 Z" fill="#FFFFFF" />
          <path d="M29 24 L37 10 L41 10 L33 24 Z" fill="#FFFFFF" />
        </g>
      </g>
    </svg>
  );
}

function IconWeatherIssue() {
  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0"
      aria-hidden="true"
    >
      {/* Vibrant solid blue cloud */}
      <path
        d="M12 21h12a5.5 5.5 0 0 0 1-10.9A7 7 0 0 0 13.5 8 5.2 5.2 0 0 0 12 21z"
        fill="#2563EB"
      />
      {/* Golden lightning bolt */}
      <polygon
        points="22.5,16 19,22 21.5,22 18,29 24,23 21,23"
        fill="#F59E0B"
      />
      {/* Rain droplets */}
      <path
        d="M11 24.5c0 1-.7 1.8-1.5 1.8s-1.5-.8-1.5-1.8c0-1 1.5-2.7 1.5-2.7s1.5 1.7 1.5 2.7z"
        fill="#3B82F6"
      />
      <path
        d="M15 26.5c0 1-.7 1.8-1.5 1.8s-1.5-.8-1.5-1.8c0-1 1.5-2.7 1.5-2.7s1.5 1.7 1.5 2.7z"
        fill="#3B82F6"
      />
    </svg>
  );
}

function IconOtherIssue() {
  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0"
      aria-hidden="true"
    >
      <circle cx="18" cy="18" r="13" stroke="#1E293B" strokeWidth="2.8" fill="none" />
      <line x1="18" y1="11.5" x2="18" y2="19" stroke="#1E293B" strokeWidth="2.8" strokeLinecap="round" />
      <circle cx="18" cy="24" r="1.6" fill="#1E293B" />
    </svg>
  );
}

const INCIDENT_TYPES: Array<{
  id: DriverIncidentType;
  label: string;
  icon: React.ReactNode;
}> = [
  { id: "landslide", label: "Landslide", icon: <IconLandslide /> },
  { id: "road_block", label: "Road Block", icon: <IconRoadBlock /> },
  { id: "weather", label: "Weather Issue", icon: <IconWeatherIssue /> },
  { id: "other", label: "Other Issue", icon: <IconOtherIssue /> },
];

function ReportHazardFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const typeParam = (searchParams.get("type") as DriverIncidentType) || "landslide";

  const [incidentType, setIncidentType] = useState<DriverIncidentType>(typeParam);
  const [description, setDescription] = useState("");

  // Location and Geocoding State
  const [locationText, setLocationText] = useState("NH-27, near Bomdila, Arunachal Pradesh");
  const [coords, setCoords] = useState<[number, number] | null>([92.4159, 27.2645]);
  const [suggestions, setSuggestions] = useState<GeocodeSuggestion[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isReverseGeocoding, setIsReverseGeocoding] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Refs for debouncing, outside click, and stale request cancellation
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const activeReqIdRef = useRef(0);
  const abortCtrlRef = useRef<AbortController | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    success: boolean;
    message: string;
    incidentId?: string;
  } | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ [key: string]: string }>({});

  const [backendInfo, setBackendInfo] = useState<BackendInfoResponse | null>(null);
  const [roadsData, setRoadsData] = useState<RoadFeatureCollection | null>(null);

  useEffect(() => {
    api.get<BackendInfoResponse>("/backend-api/info")
      .then((data) => setBackendInfo(data))
      .catch(() => {});

    api.get<RoadFeatureCollection>("/api/v1/roads/geojson?limit=500")
      .then((data) => setRoadsData(data))
      .catch(() => {});
  }, []);

  // Close suggestions dropdown when clicking outside
  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
        setActiveIndex(-1);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  // Cleanup pending search on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      if (abortCtrlRef.current) abortCtrlRef.current.abort();
    };
  }, []);

  // Debounced Autocomplete Search Handler
  const triggerDebouncedSearch = useCallback((query: string) => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    const trimmed = query.trim();
    if (trimmed.length < 3) {
      setSuggestions([]);
      setIsDropdownOpen(false);
      setIsSearching(false);
      setSearchError(null);
      return;
    }

    setIsSearching(true);
    setIsDropdownOpen(true);
    setSearchError(null);

    searchTimeoutRef.current = setTimeout(async () => {
      const currentReqId = ++activeReqIdRef.current;

      if (abortCtrlRef.current) {
        abortCtrlRef.current.abort();
      }
      abortCtrlRef.current = new AbortController();

      try {
        const results = await searchLocations(trimmed, abortCtrlRef.current.signal);
        // Guard against stale response overwriting newer queries
        if (currentReqId === activeReqIdRef.current) {
          setSuggestions(results);
          setActiveIndex(-1);
          setIsSearching(false);
        }
      } catch (err: unknown) {
        if (currentReqId === activeReqIdRef.current) {
          if (err instanceof Error && err.name === "AbortError") return;
          console.error("Location search error:", err);
          setSearchError("Unable to search locations. Click the map to pin coordinates directly.");
          setIsSearching(false);
        }
      }
    }, 350);
  }, []);

  // Handle Location Input Text Change
  const handleLocationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setLocationText(val);

    // Invalidate previous coordinates when user manually edits text
    // Never silently submit stale coordinates that do not match the displayed location
    setCoords(null);

    if (fieldErrors.location) {
      setFieldErrors((prev) => { const next = { ...prev }; delete next.location; return next; });
    }

    triggerDebouncedSearch(val);
  };

  // Handle Suggestion Selection
  const handleSelectSuggestion = (suggestion: GeocodeSuggestion) => {
    setLocationText(suggestion.displayName);
    setCoords([suggestion.lon, suggestion.lat]); // [lng, lat]
    setIsDropdownOpen(false);
    setActiveIndex(-1);
    setSuggestions([]);

    if (fieldErrors.location) {
      setFieldErrors((prev) => { const next = { ...prev }; delete next.location; return next; });
    }
  };

  // Keyboard navigation for suggestions
  const handleLocationKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownOpen || suggestions.length === 0) {
      if (e.key === "ArrowDown" && locationText.trim().length >= 3) {
        e.preventDefault();
        triggerDebouncedSearch(locationText);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        e.preventDefault();
        handleSelectSuggestion(suggestions[activeIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsDropdownOpen(false);
      setActiveIndex(-1);
    }
  };

  // Reverse geocoding when user clicks the map
  const handleMapClick = async (newCoords: [number, number]) => {
    // 1. Immediately store exact clicked coordinates for payload and pin marker
    setCoords(newCoords);
    setIsDropdownOpen(false);
    setIsReverseGeocoding(true);

    if (fieldErrors.location) {
      setFieldErrors((prev) => { const next = { ...prev }; delete next.location; return next; });
    }

    // 2. Call reverse geocoding to resolve coordinates to a real-world address
    try {
      const address = await reverseGeocodeCoordinates(newCoords[1], newCoords[0]);
      setLocationText(address);
    } catch (err: unknown) {
      console.warn("Reverse geocode failed:", err);
      setLocationText(`Selected location (${newCoords[1].toFixed(4)}, ${newCoords[0].toFixed(4)})`);
    } finally {
      setIsReverseGeocoding(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).slice(0, 5);
      setFiles(selected);
    }
  };

  const validate = () => {
    const errors: { [key: string]: string } = {};
    if (!description.trim()) {
      errors.description = "Please provide details about the road condition.";
    } else if (description.length > 500) {
      errors.description = "Description cannot exceed 500 characters.";
    }
    if (!locationText.trim()) {
      errors.location = "Location description is required.";
    } else if (!coords) {
      errors.location = "Please select a suggestion from the dropdown or click on the map to confirm coordinates.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate() || !coords) return;

    setIsSubmitting(true);
    setSubmitResult(null);

    // Map UI incident types to backend enum IncidentType
    let backendType = "LANDSLIDE";
    if (incidentType === "road_block") backendType = "ROAD_COLLAPSE";
    else if (incidentType === "weather") backendType = "FLASH_FLOOD";
    else if (incidentType === "other") backendType = "OTHER";

    const payload = {
      incident_type: backendType,
      severity: "HIGH",
      latitude: coords[1],
      longitude: coords[0],
      description: description,
      observed_at: new Date().toISOString(),
      client_report_id: `driver-report-${Date.now()}`,
      source: "FIELD_REPORT",
    };

    const isDriver = user?.role === "driver";
    let incidentId: string | null = null;
    let uploadedEvidenceCount = 0;

    try {
      if (!isDriver) {
        const data = await api.post<{ id: string }>("/api/v1/incidents", payload);
        incidentId = data.id;
      }

      // Ingest attached photographic evidence files
      if (files.length > 0) {
        for (const file of files) {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("source_type", isDriver ? "DRIVER" : "FIELD_OFFICER");
          formData.append("latitude", String(coords[1]));
          formData.append("longitude", String(coords[0]));
          if (incidentId) {
            formData.append("incident_id", incidentId);
          }
          try {
            await api.upload("/api/v1/evidence/upload", formData);
            uploadedEvidenceCount++;
          } catch (uploadErr) {
            console.warn("Evidence photo upload failed:", uploadErr);
          }
        }
      }

      if (isDriver) {
        setSubmitResult({
          success: true,
          message: `Hazard telemetry and ${uploadedEvidenceCount}/${files.length} photo(s) submitted to dispatch via evidence ingestion pipeline. Formal incident triage will be conducted by Field Operations.`,
        });
      } else {
        const evidenceMsg =
          files.length > 0
            ? ` and ${uploadedEvidenceCount}/${files.length} photo(s) persisted`
            : "";
        setSubmitResult({
          success: true,
          message: `Report successfully registered with dispatch operations${evidenceMsg}. Queued for verification.`,
          incidentId: incidentId || undefined,
        });
      }
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
          ? err.message
          : "Failed to submit report.";
      setSubmitResult({
        success: false,
        message: msg,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const hazardMarker = coords
    ? {
        lngLat: coords,
        label: incidentType.toUpperCase(),
      }
    : null;

  return (
    <div className="max-w-7xl mx-auto w-full flex flex-col gap-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-[#193B32] tracking-tight">
          Report a Road Hazard
        </h1>
        <p className="text-sm text-[#71877D] mt-1">
          Help keep routes safe by reporting road conditions in real time.
        </p>
      </div>

      {submitResult && (
        <div
          role="alert"
          className={`p-4 sm:p-5 rounded-2xl border text-sm leading-relaxed ${
            submitResult.success
              ? "bg-[#DDF4E8] border-[#B7E4CD] text-[#12432A]"
              : "bg-[#FFF8EB] border-[#FCE1B6] text-[#A66007]"
          }`}
        >
          <div className="flex items-center gap-2 font-bold mb-1.5">
            <span className="text-base">{submitResult.success ? "✓" : "ℹ"}</span>
            <span className="text-sm sm:text-base">{submitResult.success ? "Submission Confirmed" : "Operational Status Note"}</span>
          </div>
          <p className="text-sm">{submitResult.message}</p>
          {submitResult.incidentId && (
            <p className="font-mono text-xs mt-1.5">Incident ID: {submitResult.incidentId}</p>
          )}
          <div className="mt-4 flex gap-2.5">
            <button
              type="button"
              onClick={() => router.push("/driver")}
              className="px-4 py-1.5 bg-[#12432A] text-white rounded-full text-xs font-semibold hover:bg-[#0d3420] transition-colors"
            >
              Back to Dashboard
            </button>
            <button
              type="button"
              onClick={() => setSubmitResult(null)}
              className="px-4 py-1.5 bg-white border border-[#DCE5D8] text-[#193B32] rounded-full text-xs font-semibold hover:bg-[#FAFBF7] transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Grid Layout: Left Form + Right Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form (7 cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-7 rx-card p-6 sm:p-7 flex flex-col gap-5">
          {/* 1. Incident Type Selector */}
          <div>
            <label className="block text-sm font-semibold text-[#193B32] mb-3">
              Incident Type
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
              {INCIDENT_TYPES.map((type) => {
                const isSelected = incidentType === type.id;
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setIncidentType(type.id)}
                    className={`flex flex-col items-center justify-center p-4 sm:p-5 rounded-2xl text-center transition-all cursor-pointer min-h-[110px] sm:min-h-[125px] ${
                      isSelected
                        ? "bg-[#EAF5EE] border-2 border-[#16A779] shadow-xs"
                        : "bg-white border border-[#E5E7EB] hover:border-[#CBD5E1] hover:bg-[#FAFBF7]"
                    }`}
                  >
                    <div className="mb-2.5 flex items-center justify-center">
                      {type.icon}
                    </div>
                    <span
                      className={`text-[14.5px] font-bold tracking-tight ${
                        isSelected ? "text-[#12432A]" : "text-[#193B32]"
                      }`}
                    >
                      {type.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. Description Field */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="hazard-desc" className="text-sm font-semibold text-[#193B32]">
                Description
              </label>
              <span className="text-xs text-[#71877D] font-mono">{description.length}/500</span>
            </div>
            <textarea
              id="hazard-desc"
              rows={3}
              maxLength={500}
              placeholder="Provide details about the incident condition, obstructions, and road status..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`w-full p-3.5 rounded-xl bg-white border text-sm text-[#193B32] outline-none focus:border-[#16A779] transition-colors leading-relaxed ${
                fieldErrors.description ? "border-[#DC4848]" : "border-[#DCE5D8]"
              }`}
            />
            {fieldErrors.description && (
              <p className="text-xs text-[#DC4848] mt-1.5 font-medium">{fieldErrors.description}</p>
            )}
          </div>

          {/* 3. Location Field with Autocomplete & Reverse Geocoding */}
          <div ref={dropdownRef} className="relative">
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="hazard-loc" className="block text-sm font-semibold text-[#193B32]">
                Location
              </label>
              {isReverseGeocoding ? (
                <span className="text-xs text-[#16A779] font-medium flex items-center gap-1.5">
                  <span className="w-3 h-3 border-2 border-[#16A779] border-t-transparent rounded-full animate-spin" />
                  Resolving map address...
                </span>
              ) : coords ? (
                <span className="text-[11px] font-mono text-[#5F756B] flex items-center gap-1">
                  <span className="text-[#16A779] font-bold">✓</span>
                  <span>[{coords[1].toFixed(4)}, {coords[0].toFixed(4)}]</span>
                </span>
              ) : null}
            </div>

            <div className="relative">
              {/* Map pin icon */}
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#71877D] flex items-center pointer-events-none">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#71877D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </span>

              {/* Location Input */}
              <input
                id="hazard-loc"
                type="text"
                autoComplete="off"
                role="combobox"
                aria-expanded={isDropdownOpen}
                aria-autocomplete="list"
                aria-controls="location-suggestions-list"
                aria-activedescendant={activeIndex >= 0 ? `suggestion-${activeIndex}` : undefined}
                value={locationText}
                onChange={handleLocationChange}
                onKeyDown={handleLocationKeyDown}
                onFocus={() => {
                  if (locationText.trim().length >= 3 && suggestions.length > 0) {
                    setIsDropdownOpen(true);
                  }
                }}
                placeholder="Type road, village, town or landmark across India..."
                className={`w-full py-2.5 pl-10 pr-9 rounded-xl bg-white border text-sm text-[#193B32] outline-none focus:border-[#16A779] transition-colors ${
                  fieldErrors.location ? "border-[#DC4848]" : "border-[#DCE5D8]"
                }`}
              />

              {/* Right status icon (spinner while searching or clear button) */}
              {isSearching ? (
                <span className="absolute right-3.5 top-1/2 -translate-y-1/2 flex items-center">
                  <span className="w-4 h-4 border-2 border-[#16A779] border-t-transparent rounded-full animate-spin" />
                </span>
              ) : locationText ? (
                <button
                  type="button"
                  title="Clear location"
                  onClick={() => {
                    setLocationText("");
                    setCoords(null);
                    setSuggestions([]);
                    setIsDropdownOpen(false);
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-[#71877D] hover:text-[#193B32] rounded-full hover:bg-[#F1F4E8] text-xs transition-colors"
                >
                  ✕
                </button>
              ) : null}

              {/* Suggestions Dropdown */}
              {isDropdownOpen && (
                <div className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-white border border-[#DCE5D8] rounded-xl shadow-lg max-h-64 overflow-y-auto overflow-x-hidden">
                  {isSearching ? (
                    <div className="p-3.5 text-xs text-[#71877D] flex items-center justify-center gap-2">
                      <span className="w-3.5 h-3.5 border-2 border-[#16A779] border-t-transparent rounded-full animate-spin" />
                      <span>Searching locations across India...</span>
                    </div>
                  ) : searchError ? (
                    <div className="p-3.5 text-xs text-[#B45309] text-center bg-[#FFF8EB]">
                      {searchError}
                    </div>
                  ) : suggestions.length === 0 ? (
                    <div className="p-3.5 text-xs text-[#71877D] text-center">
                      No places found matching &ldquo;{locationText}&rdquo;. Try entering a nearby road, town, village, or district.
                    </div>
                  ) : (
                    <ul role="listbox" id="location-suggestions-list" className="py-1">
                      {suggestions.map((item, idx) => {
                        const isHighlighted = idx === activeIndex;
                        return (
                          <li
                            key={item.id}
                            id={`suggestion-${idx}`}
                            role="option"
                            aria-selected={isHighlighted}
                            onClick={() => handleSelectSuggestion(item)}
                            onMouseEnter={() => setActiveIndex(idx)}
                            className={`px-3.5 py-2.5 cursor-pointer flex items-start gap-2.5 transition-colors border-b border-[#F5F8F3] last:border-b-0 ${
                              isHighlighted ? "bg-[#EAF5EE] text-[#12432A]" : "hover:bg-[#FAFBF7] text-[#193B32]"
                            }`}
                          >
                            <span className="mt-0.5 text-[#16A779] shrink-0">
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                                <circle cx="12" cy="10" r="3" />
                              </svg>
                            </span>
                            <div className="flex flex-col min-w-0 flex-1">
                              <span className="text-sm font-semibold truncate leading-snug">
                                {item.name}
                              </span>
                              <span className="text-xs text-[#71877D] truncate mt-0.5 leading-snug">
                                {item.secondaryText}
                              </span>
                            </div>
                            <span className="text-[10px] uppercase font-bold text-[#71877D] bg-[#F1F4E8] px-1.5 py-0.5 rounded self-center shrink-0">
                              IN
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </div>

            {/* Error or guidance text */}
            {fieldErrors.location ? (
              <p className="text-xs text-[#DC4848] mt-1.5 font-medium">{fieldErrors.location}</p>
            ) : !coords && locationText.trim().length >= 3 && !isSearching ? (
              <p className="text-xs text-[#B45309] mt-1.5 flex items-center gap-1 font-medium">
                <span>ℹ</span>
                <span>Select a location suggestion from the dropdown, or click anywhere on the map to confirm coordinates.</span>
              </p>
            ) : (
              <p className="text-xs text-[#71877D] mt-1.5">
                Tip: Type a road or place name to pick a suggestion, or click anywhere on the map to automatically reverse-geocode coordinates.
              </p>
            )}
          </div>

          {/* 4. Add Photos (Optional) */}
          <div>
            <label className="block text-sm font-semibold text-[#193B32] mb-1.5">
              Add Photos (Optional)
            </label>
            <label
              htmlFor="hazard-photos"
              className="border-2 border-dashed border-[#DCE5D8] hover:border-[#16A779] rounded-xl p-5 sm:p-6 flex flex-col items-center justify-center cursor-pointer bg-[#FAFBF7] hover:bg-white transition-all text-center"
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#71877D" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mb-2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
              <span className="text-sm font-semibold text-[#193B32]">
                {files.length > 0 ? `${files.length} file(s) selected` : "Drag and drop images or click to upload"}
              </span>
              <span className="text-xs text-[#71877D] mt-1">PNG, JPG (Max 5 images, 10 MB each)</span>
              <input
                id="hazard-photos"
                type="file"
                multiple
                accept="image/png, image/jpeg"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
            {files.length > 0 && (
              <p className="text-xs text-[#12432A] mt-2 font-semibold">
                ✓ {files.length} evidence photo(s) selected for upload and operational verification.
              </p>
            )}
          </div>

          {/* Buttons: Cancel & Submit Report */}
          <div className="pt-4 mt-1 border-t border-[#E8EFE5] flex items-center justify-end gap-3">
            <Link
              href="/driver"
              className="px-6 py-2.5 rounded-full border border-[#DCE5D8] text-sm font-semibold text-[#193B32] hover:bg-[#FAFBF7] transition-colors"
            >
              Cancel
            </Link>

            <button
              type="submit"
              disabled={isSubmitting}
              className="rx-btn-primary px-6 py-2.5 text-sm font-semibold inline-flex items-center gap-2"
            >
              {isSubmitting ? (
                <span>Submitting...</span>
              ) : (
                <>
                  <span>Submit Report</span>
                  <span aria-hidden="true">→</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Right Map Preview (5 cols) */}
        <div className="lg:col-span-5 rx-card p-0 overflow-hidden relative min-h-[380px] h-full flex flex-col">
          <div className="p-3.5 bg-white border-b border-[#DCE5D8] flex items-center justify-between z-10">
            <span className="text-sm font-bold text-[#193B32]">Selected Location Map</span>
            <span className="text-xs font-mono text-[#71877D]">
              {coords ? `Lat: ${coords[1].toFixed(4)}, Lng: ${coords[0].toFixed(4)}` : "Click map to pin point"}
            </span>
          </div>

          <div className="flex-1 relative min-h-[340px] bg-[#EAF2E7]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              hazardMarker={hazardMarker}
              customCenter={coords || [92.4159, 27.2645]}
              customZoom={8.5}
              onMapClick={handleMapClick}
              className="w-full h-full relative"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReportIncidentPage() {
  return (
    <DriverLayout>
      <Suspense fallback={<div className="p-6 text-sm text-[#71877D]">Loading hazard reporting form...</div>}>
        <ReportHazardFormContent />
      </Suspense>
    </DriverLayout>
  );
}
