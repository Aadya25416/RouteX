"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, ApiError } from "./api";

export interface GpsFix {
  latitude: number;
  longitude: number;
  accuracy: number;
  speedKmh: number | null;
  headingDeg: number | null;
  timestamp: string;
}

export interface UseGpsTrackerOptions {
  minIntervalMs?: number; // Target GPS push cadence (default: 5000ms / 5s)
  onFixSent?: (fix: GpsFix) => void;
  onError?: (errorMsg: string) => void;
}

export interface UseGpsTrackerReturn {
  isTracking: boolean;
  isSyncing: boolean;
  lastFix: GpsFix | null;
  lastSyncedAt: string | null;
  syncCount: number;
  trackingError: string | null;
  startTracking: (vehicleId: string, tripId?: string | null) => void;
  stopTracking: () => void;
}

export function useGpsTracker(options: UseGpsTrackerOptions = {}): UseGpsTrackerReturn {
  const { minIntervalMs = 5000, onFixSent, onError } = options;

  const [isTracking, setIsTracking] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [lastFix, setLastFix] = useState<GpsFix | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [syncCount, setSyncCount] = useState<number>(0);
  const [trackingError, setTrackingError] = useState<string | null>(null);

  const watchIdRef = useRef<number | null>(null);
  const activeVehicleIdRef = useRef<string | null>(null);
  const activeTripIdRef = useRef<string | null>(null);
  const lastPushTimeRef = useRef<number>(0);
  const latestRecordedAtRef = useRef<string | null>(null);

  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null && typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    activeVehicleIdRef.current = null;
    activeTripIdRef.current = null;
    setIsTracking(false);
    setIsSyncing(false);
  }, []);

  const handlePositionSuccess = useCallback(
    async (pos: GeolocationPosition) => {
      const vehicleId = activeVehicleIdRef.current;
      if (!vehicleId) return;

      const nowMs = Date.now();
      const speedKmh =
        pos.coords.speed != null && !isNaN(pos.coords.speed) && pos.coords.speed >= 0
          ? Math.round(pos.coords.speed * 3.6 * 10) / 10
          : null;
      const headingDeg =
        pos.coords.heading != null && !isNaN(pos.coords.heading) && pos.coords.heading >= 0
          ? Math.round(pos.coords.heading)
          : null;

      const fixTime = new Date(pos.timestamp || nowMs).toISOString();

      const currentFix: GpsFix = {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy: Math.round(pos.coords.accuracy || 0),
        speedKmh,
        headingDeg,
        timestamp: fixTime,
      };

      setLastFix(currentFix);
      setTrackingError(null);

      // Enforce update interval throttling (~5s) unless this is the very first fix
      if (nowMs - lastPushTimeRef.current < minIntervalMs && lastPushTimeRef.current !== 0) {
        return;
      }

      // Check monotonicity
      if (latestRecordedAtRef.current && fixTime <= latestRecordedAtRef.current) {
        return;
      }

      setIsSyncing(true);
      lastPushTimeRef.current = nowMs;

      const payload = {
        latitude: currentFix.latitude,
        longitude: currentFix.longitude,
        speed_kmh: currentFix.speedKmh,
        heading_deg: currentFix.headingDeg,
        source: "gps_driver_app",
        recorded_at: fixTime,
        trip_id: activeTripIdRef.current || undefined,
      };

      try {
        await api.post(`/api/v1/vehicles/${vehicleId}/locations`, payload);
        latestRecordedAtRef.current = fixTime;
        const syncTimeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        setLastSyncedAt(syncTimeStr);
        setSyncCount((c) => c + 1);
        if (onFixSent) onFixSent(currentFix);
      } catch (err: unknown) {
        let msg = "Telemetry sync failed.";
        if (err instanceof ApiError) {
          msg = err.message;
        } else if (err instanceof Error) {
          msg = err.message;
        }
        setTrackingError(msg);
        if (onError) onError(msg);
      } finally {
        setIsSyncing(false);
      }
    },
    [minIntervalMs, onFixSent, onError]
  );

  const handlePositionError = useCallback(
    (err: GeolocationPositionError) => {
      let errorMsg = "Unable to retrieve device GPS coordinates.";
      if (err.code === err.PERMISSION_DENIED) {
        errorMsg = "Location permission denied. Please allow GPS access in your browser settings.";
      } else if (err.code === err.POSITION_UNAVAILABLE) {
        errorMsg = "GPS signal unavailable. Ensure location services are active.";
      } else if (err.code === err.TIMEOUT) {
        errorMsg = "GPS acquisition timed out. Reacquiring satellite fix...";
      }
      setTrackingError(errorMsg);
      if (onError) onError(errorMsg);
    },
    [onError]
  );

  const startTracking = useCallback(
    (vehicleId: string, tripId?: string | null) => {
      if (!vehicleId) {
        setTrackingError("No assigned vehicle found to associate telemetry with.");
        return;
      }

      if (typeof window === "undefined" || !("geolocation" in navigator)) {
        setTrackingError("Geolocation is not supported by your browser or device.");
        return;
      }

      // Stop previous watcher if active
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }

      setTrackingError(null);
      activeVehicleIdRef.current = vehicleId;
      activeTripIdRef.current = tripId || null;
      lastPushTimeRef.current = 0;

      try {
        const id = navigator.geolocation.watchPosition(
          handlePositionSuccess,
          handlePositionError,
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 3000,
          }
        );
        watchIdRef.current = id;
        setIsTracking(true);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to initialize GPS tracking.";
        setTrackingError(msg);
      }
    },
    [handlePositionSuccess, handlePositionError]
  );

  // Clean up watcher when hook unmounts
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null && typeof navigator !== "undefined" && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, []);

  return {
    isTracking,
    isSyncing,
    lastFix,
    lastSyncedAt,
    syncCount,
    trackingError,
    startTracking,
    stopTracking,
  };
}
