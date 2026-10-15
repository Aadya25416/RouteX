"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import DriverLayout from "@/components/driver/DriverLayout";
import { DriverIncidentType } from "@/types/driver";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
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
  const [locationText, setLocationText] = useState("NH-27, near Bomdila, Arunachal Pradesh");
  const [coords, setCoords] = useState<[number, number]>([92.4159, 27.2645]);
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

  const handleMapClick = (newCoords: [number, number]) => {
    setCoords(newCoords);
    setLocationText(`Corridor coordinate [${newCoords[1].toFixed(4)}, ${newCoords[0].toFixed(4)}]`);
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
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

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

  const hazardMarker = {
    lngLat: coords,
    label: incidentType.toUpperCase(),
  };

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

          {/* 3. Location Field */}
          <div>
            <label htmlFor="hazard-loc" className="block text-sm font-semibold text-[#193B32] mb-1.5">
              Location
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#71877D] flex items-center pointer-events-none">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#71877D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </span>
              <input
                id="hazard-loc"
                type="text"
                value={locationText}
                onChange={(e) => setLocationText(e.target.value)}
                placeholder="NH-27, near Bomdila, Arunachal Pradesh"
                className={`w-full py-2.5 pl-10 pr-3.5 rounded-xl bg-white border text-sm text-[#193B32] outline-none focus:border-[#16A779] transition-colors ${
                  fieldErrors.location ? "border-[#DC4848]" : "border-[#DCE5D8]"
                }`}
              />
            </div>
            <p className="text-xs text-[#71877D] mt-1.5">
              Tip: Click anywhere on the map to pin exact incident coordinates.
            </p>
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
              Lat: {coords[1].toFixed(3)}, Lng: {coords[0].toFixed(3)}
            </span>
          </div>

          <div className="flex-1 relative min-h-[340px] bg-[#EAF2E7]">
            <RoadMap
              backendInfo={backendInfo}
              roadsData={roadsData}
              hazardMarker={hazardMarker}
              customCenter={coords}
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
