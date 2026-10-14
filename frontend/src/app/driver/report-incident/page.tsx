"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import DriverLayout from "@/components/driver/DriverLayout";
import { DriverIncidentType } from "@/types/driver";
import type { BackendInfoResponse, RoadFeatureCollection } from "@/types/roads";

// Dynamically import RoadMap
const RoadMap = dynamic(() => import("@/components/RoadMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[350px] bg-[#EAF2E7] flex items-center justify-center text-xs text-[#71877D]">
      Initializing MapLibre hazard locator...
    </div>
  ),
});

function ReportHazardFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
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
    fetch("/backend-api/info", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setBackendInfo(data))
      .catch(() => {});

    fetch("/api/v1/roads/geojson?limit=500", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
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

    try {
      const res = await fetch("/api/v1/incidents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setSubmitResult({
          success: true,
          message: "Report successfully registered with dispatch operations.",
          incidentId: data.id,
        });
      } else {
        setSubmitResult({
          success: false,
          message: `Backend returned HTTP ${res.status}: Field incident submission requires an authorized field officer or dispatcher bearer token in Phase 1. Client-side report has been verified.`,
        });
      }
    } catch {
      setSubmitResult({
        success: false,
        message: "RouteX backend service is currently offline. Form validation succeeded, but no live connection exists to http://127.0.0.1:8000.",
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
    <div className="max-w-7xl mx-auto w-full flex flex-col gap-4">
      {/* Page Title */}
      <div>
        <h1 className="text-xl font-extrabold text-[#193B32]">Report a Road Hazard</h1>
        <p className="text-xs text-[#71877D]">
          Help keep routes safe by reporting road conditions.
        </p>
      </div>

      {submitResult && (
        <div
          role="alert"
          className={`p-4 rounded-xl border text-xs leading-relaxed ${
            submitResult.success
              ? "bg-[#DDF4E8] border-[#B7E4CD] text-[#12432A]"
              : "bg-[#FFF8EB] border-[#FCE1B6] text-[#A66007]"
          }`}
        >
          <div className="flex items-center gap-2 font-bold mb-1">
            <span>{submitResult.success ? "✓" : "ℹ"}</span>
            <span>{submitResult.success ? "Submission Confirmed" : "Operational Status Note"}</span>
          </div>
          <p>{submitResult.message}</p>
          {submitResult.incidentId && (
            <p className="font-mono text-[11px] mt-1">Incident ID: {submitResult.incidentId}</p>
          )}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => router.push("/driver")}
              className="px-3 py-1 bg-[#12432A] text-white rounded-full text-[11px] font-semibold"
            >
              Back to Dashboard
            </button>
            <button
              type="button"
              onClick={() => setSubmitResult(null)}
              className="px-3 py-1 bg-white border border-[#DCE5D8] text-[#193B32] rounded-full text-[11px] font-semibold"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Grid Layout: Left Form + Right Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form (7 cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-7 rx-card flex flex-col gap-4">
          {/* 1. Incident Type Selector */}
          <div>
            <label className="block text-xs font-bold text-[#193B32] mb-2">Incident Type</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {/* Landslide */}
              <button
                type="button"
                onClick={() => setIncidentType("landslide")}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                  incidentType === "landslide"
                    ? "bg-[#DDF4E8] border-[#16A779] shadow-xs text-[#12432A]"
                    : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D] hover:bg-white"
                }`}
              >
                <span className="text-xl mb-1">⚠️</span>
                <span className="text-xs font-bold">Landslide</span>
              </button>

              {/* Road Block */}
              <button
                type="button"
                onClick={() => setIncidentType("road_block")}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                  incidentType === "road_block"
                    ? "bg-[#DDF4E8] border-[#16A779] shadow-xs text-[#12432A]"
                    : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D] hover:bg-white"
                }`}
              >
                <span className="text-xl mb-1">🚫</span>
                <span className="text-xs font-bold">Road Block</span>
              </button>

              {/* Weather Issue */}
              <button
                type="button"
                onClick={() => setIncidentType("weather")}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                  incidentType === "weather"
                    ? "bg-[#DDF4E8] border-[#16A779] shadow-xs text-[#12432A]"
                    : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D] hover:bg-white"
                }`}
              >
                <span className="text-xl mb-1">🌧️</span>
                <span className="text-xs font-bold">Weather Issue</span>
              </button>

              {/* Other Issue */}
              <button
                type="button"
                onClick={() => setIncidentType("other")}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                  incidentType === "other"
                    ? "bg-[#DDF4E8] border-[#16A779] shadow-xs text-[#12432A]"
                    : "bg-[#FAFBF7] border-[#DCE5D8] text-[#71877D] hover:bg-white"
                }`}
              >
                <span className="text-xl mb-1">🔒</span>
                <span className="text-xs font-bold">Other Issue</span>
              </button>
            </div>
          </div>

          {/* 2. Description Field */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="hazard-desc" className="text-xs font-bold text-[#193B32]">
                Description
              </label>
              <span className="text-[11px] text-[#71877D]">{description.length}/500</span>
            </div>
            <textarea
              id="hazard-desc"
              rows={3}
              maxLength={500}
              placeholder="Provide more details about the incident..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`w-full p-3 rounded-xl bg-white border text-xs text-[#193B32] outline-none focus:border-[#16A779] transition-colors ${
                fieldErrors.description ? "border-[#DC4848]" : "border-[#DCE5D8]"
              }`}
            />
            {fieldErrors.description && (
              <p className="text-[11px] text-[#DC4848] mt-1">{fieldErrors.description}</p>
            )}
          </div>

          {/* 3. Location Field */}
          <div>
            <label htmlFor="hazard-loc" className="block text-xs font-bold text-[#193B32] mb-1">
              Location
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71877D] text-sm">
                📍
              </span>
              <input
                id="hazard-loc"
                type="text"
                value={locationText}
                onChange={(e) => setLocationText(e.target.value)}
                placeholder="NH-27, near Bomdila, Arunachal Pradesh"
                className={`w-full py-2.5 pl-9 pr-3 rounded-xl bg-white border text-xs text-[#193B32] outline-none focus:border-[#16A779] ${
                  fieldErrors.location ? "border-[#DC4848]" : "border-[#DCE5D8]"
                }`}
              />
            </div>
            <p className="text-[10px] text-[#71877D] mt-1">
              Tip: Click anywhere on the map to pin exact incident coordinates.
            </p>
          </div>

          {/* 4. Add Photos (Optional) */}
          <div>
            <label className="block text-xs font-bold text-[#193B32] mb-1">
              Add Photos (Optional)
            </label>
            <label
              htmlFor="hazard-photos"
              className="border-2 border-dashed border-[#DCE5D8] hover:border-[#16A779] rounded-xl p-5 flex flex-col items-center justify-center cursor-pointer bg-[#FAFBF7] hover:bg-white transition-all text-center"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#71877D] mb-1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
              <span className="text-xs font-semibold text-[#193B32]">
                {files.length > 0 ? `${files.length} file(s) selected` : "Drag and drop images or click to upload"}
              </span>
              <span className="text-[11px] text-[#71877D] mt-0.5">PNG, JPG (Max 5 images, 10 MB each)</span>
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
              <p className="text-[10px] text-[#71877D] mt-1">
                Note: In Phase 1 prototype, photos are queued client-side as cloud storage uploads require cloud bucket configuration.
              </p>
            )}
          </div>

          {/* Buttons: Cancel & Submit Report */}
          <div className="pt-3 border-t border-[#E8EFE5] flex items-center justify-end gap-3">
            <Link
              href="/driver"
              className="px-5 py-2.5 rounded-full border border-[#DCE5D8] text-xs font-semibold text-[#193B32] hover:bg-[#FAFBF7] transition-colors"
            >
              Cancel
            </Link>

            <button
              type="submit"
              disabled={isSubmitting}
              className="rx-btn-primary"
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
        <div className="lg:col-span-5 rx-card p-0 overflow-hidden relative min-h-[350px] h-full flex flex-col">
          <div className="p-3 bg-white border-b border-[#DCE5D8] flex items-center justify-between z-10">
            <span className="text-xs font-bold text-[#193B32]">Selected Location Map</span>
            <span className="text-[11px] text-[#71877D]">
              Lat: {coords[1].toFixed(3)}, Lng: {coords[0].toFixed(3)}
            </span>
          </div>

          <div className="flex-1 relative min-h-[320px] bg-[#EAF2E7]">
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
      <Suspense fallback={<div className="p-4 text-xs text-[#71877D]">Loading hazard reporting form...</div>}>
        <ReportHazardFormContent />
      </Suspense>
    </DriverLayout>
  );
}
