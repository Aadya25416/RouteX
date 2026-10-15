"use client";

import React, { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { AlertItem, AlertListResponse, AlertAcknowledgeResponse, AlertSeverity } from "@/types/alerts";

interface AlertsPanelProps {
  className?: string;
  onAlertAcknowledged?: () => void;
  sseEvent?: { event_type: string; payload?: unknown } | null;
}

function formatAlertTimestamp(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "Recently";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "Recently";
  }
}

function getSeverityBadge(severity: AlertSeverity) {
  switch (severity.toLowerCase()) {
    case "critical":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase bg-red-100 text-red-800 border border-red-300">
          <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-ping" />
          CRITICAL
        </span>
      );
    case "high":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-orange-100 text-orange-800 border border-orange-300">
          HIGH
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-amber-100 text-amber-800 border border-amber-300">
          WARNING
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase bg-slate-100 text-slate-700 border border-slate-200">
          INFO
        </span>
      );
  }
}

export default function AlertsPanel({ className = "", onAlertAcknowledged, sseEvent }: AlertsPanelProps) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [unacknowledgedCount, setUnacknowledgedCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [filterAcknowledged, setFilterAcknowledged] = useState<string>("unack");
  const [acknowledgingIds, setAcknowledgingIds] = useState<Record<string, boolean>>({});

  const fetchAlerts = useCallback(async () => {
    try {
      let query = "/api/v1/alerts?limit=30";
      if (filterAcknowledged === "unack") {
        query += "&is_acknowledged=false";
      } else if (filterAcknowledged === "ack") {
        query += "&is_acknowledged=true";
      }
      if (filterSeverity !== "all") {
        query += `&severity=${filterSeverity}`;
      }

      const res = await api.get<AlertListResponse>(query);
      setAlerts(res.items || []);
      setUnacknowledgedCount(res.unacknowledged_count || 0);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      setIsLoading(false);
    }
  }, [filterAcknowledged, filterSeverity]);

  useEffect(() => {
    let isCancelled = false;
    const run = async () => {
      try {
        let query = "/api/v1/alerts?limit=30";
        if (filterAcknowledged === "unack") {
          query += "&is_acknowledged=false";
        } else if (filterAcknowledged === "ack") {
          query += "&is_acknowledged=true";
        }
        if (filterSeverity !== "all") {
          query += `&severity=${filterSeverity}`;
        }

        const res = await api.get<AlertListResponse>(query);
        if (!isCancelled) {
          setAlerts(res.items || []);
          setUnacknowledgedCount(res.unacknowledged_count || 0);
          setError(null);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : "Failed to load alerts");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };
    run();
    return () => {
      isCancelled = true;
    };
  }, [filterAcknowledged, filterSeverity]);

  // Handle incoming real-time SSE alerts without manual refresh
  useEffect(() => {
    if (!sseEvent) return;

    queueMicrotask(() => {
      if (sseEvent.event_type === "alert.created" && sseEvent.payload) {
        const payload = sseEvent.payload as AlertItem;
        setAlerts((prev) => {
          if (prev.some((a) => a.id === payload.id || (payload.dedup_key && a.dedup_key === payload.dedup_key))) {
            return prev;
          }
          return [payload, ...prev];
        });
        setUnacknowledgedCount((c) => c + 1);
      } else if (sseEvent.event_type === "alert.acknowledged" && sseEvent.payload) {
        const payload = sseEvent.payload as { alert_id: string; acknowledged_at?: string };
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === payload.alert_id
              ? { ...a, is_acknowledged: true, acknowledged_at: payload.acknowledged_at || new Date().toISOString() }
              : a
          )
        );
        setUnacknowledgedCount((c) => Math.max(0, c - 1));
      }
    });
  }, [sseEvent]);

  const handleAcknowledge = async (alertId: string) => {
    setAcknowledgingIds((prev) => ({ ...prev, [alertId]: true }));
    try {
      const res = await api.post<AlertAcknowledgeResponse>(`/api/v1/alerts/${alertId}/acknowledge`);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId
            ? { ...a, is_acknowledged: true, acknowledged_at: res.acknowledged_at || new Date().toISOString() }
            : a
        )
      );
      setUnacknowledgedCount((c) => Math.max(0, c - 1));
      if (onAlertAcknowledged) {
        onAlertAcknowledged();
      }
    } catch (err) {
      console.error("Acknowledgement failed:", err);
    } finally {
      setAcknowledgingIds((prev) => {
        const next = { ...prev };
        delete next[alertId];
        return next;
      });
    }
  };

  return (
    <div className={`rx-admin-card flex flex-col justify-between ${className}`}>
      <div>
        {/* Panel Header */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3 pb-2 border-b border-[#E8EFE5]">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-[#193B32]">Actionable Alerts</h2>
            {unacknowledgedCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#DC4848] text-white">
                {unacknowledgedCount} unacknowledged
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Filter: Ack state */}
            <select
              aria-label="Filter alerts acknowledgement status"
              value={filterAcknowledged}
              onChange={(e) => setFilterAcknowledged(e.target.value)}
              className="text-xs font-medium text-[#193B32] bg-[#FAFBF7] border border-[#DCE5D8] rounded-md px-2 py-1 focus:outline-none focus:border-[#16A779]"
            >
              <option value="unack">Pending</option>
              <option value="all">All</option>
              <option value="ack">Acknowledged</option>
            </select>

            {/* Filter: Severity */}
            <select
              aria-label="Filter alerts severity"
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="text-xs font-medium text-[#193B32] bg-[#FAFBF7] border border-[#DCE5D8] rounded-md px-2 py-1 focus:outline-none focus:border-[#16A779]"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>

            <button
              onClick={fetchAlerts}
              title="Refresh alerts"
              className="p-1 rounded-md text-[#71877D] hover:text-[#193B32] hover:bg-slate-100 transition-colors"
            >
              <span className="text-xs">🔄</span>
            </button>
          </div>
        </div>

        {/* Alerts Content */}
        {isLoading && alerts.length === 0 ? (
          <div className="space-y-2 py-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse p-3 rounded-xl bg-slate-50 border border-slate-100 flex flex-col gap-2">
                <div className="h-3 w-1/3 bg-slate-200 rounded" />
                <div className="h-3 w-3/4 bg-slate-200 rounded" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-center my-2">
            <p className="text-xs text-red-700 font-semibold mb-2">{error}</p>
            <button
              onClick={fetchAlerts}
              className="px-3 py-1 bg-white border border-red-300 text-xs text-red-700 rounded-md font-medium hover:bg-red-50"
            >
              Try Again
            </button>
          </div>
        ) : alerts.length === 0 ? (
          <div className="p-6 text-center text-slate-500 my-2">
            <span className="text-2xl block mb-1">🛡️</span>
            <p className="text-xs font-medium text-[#71877D]">No alerts matching filter criteria.</p>
            <p className="text-[11px] text-[#8F9E97]">Operations running normally across the corridor.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#E8EFE5] max-h-[380px] overflow-y-auto pr-1">
            {alerts.map((alert) => {
              const isAcking = !!acknowledgingIds[alert.id];
              return (
                <div key={alert.id} className="py-3 flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 mb-1">
                      {getSeverityBadge(alert.severity)}
                      {alert.entity_type && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono text-slate-600">
                          {alert.entity_type} #{alert.entity_id ? alert.entity_id.slice(0, 8) : ""}
                        </span>
                      )}
                      <span className="text-[10px] text-[#8F9E97]">
                        {formatAlertTimestamp(alert.created_at)}
                      </span>
                    </div>

                    <p className="text-xs text-[#193B32] font-medium leading-relaxed">
                      {alert.message}
                    </p>

                    {alert.is_acknowledged && (
                      <span className="inline-flex items-center gap-1 mt-1 text-[10px] text-emerald-700 font-semibold">
                        <span>✓</span>
                        <span>Acknowledged</span>
                      </span>
                    )}
                  </div>

                  {!alert.is_acknowledged && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      disabled={isAcking}
                      className="shrink-0 px-2.5 py-1 text-[11px] font-bold rounded-lg border border-[#16A779] text-[#16A779] bg-white hover:bg-emerald-50 active:bg-emerald-100 transition-colors disabled:opacity-50"
                    >
                      {isAcking ? "..." : "Acknowledge"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer info */}
      <div className="pt-3 mt-3 border-t border-[#E8EFE5] flex items-center justify-between text-xs text-[#71877D]">
        <span>Corridor alerts stream directly via Redis Streams SSE</span>
        <button
          onClick={fetchAlerts}
          className="font-semibold text-[#176B4D] hover:underline"
        >
          Refresh Feed
        </button>
      </div>
    </div>
  );
}
