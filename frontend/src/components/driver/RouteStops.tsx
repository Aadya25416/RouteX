"use client";

import React from "react";
import { TripStop } from "@/types/driver";

interface RouteStopsProps {
  stops: TripStop[];
}

export default function RouteStops({ stops }: RouteStopsProps) {
  return (
    <div className="flex flex-col w-full">
      <h2 className="text-base sm:text-lg font-semibold text-[#193B32] mb-6 tracking-tight">
        Route Stops
      </h2>

      <div className="relative flex flex-col">
        {stops.map((stop, index) => {
          const isLast = index === stops.length - 1;

          // Status marker:
          // Guwahati & Nagaon (Departed / Completed): green
          // Bomdila (Next stop): orange
          // Tawang (Destination): muted gray outlined
          let markerElement: React.ReactNode;
          if (stop.status === "Departed" || stop.status === "Completed") {
            markerElement = (
              <span
                className="w-2.5 h-2.5 rounded-full bg-[#16A779] shrink-0"
                aria-hidden="true"
              />
            );
          } else if (stop.status === "Next stop") {
            markerElement = (
              <span
                className="w-2.5 h-2.5 rounded-full bg-[#F59E0B] shrink-0"
                aria-hidden="true"
              />
            );
          } else {
            markerElement = (
              <span
                className="w-2.5 h-2.5 rounded-full border-2 border-[#9CA3AF] bg-white shrink-0"
                aria-hidden="true"
              />
            );
          }

          // Status label text color:
          // Departed: green
          // Completed: green
          // Next stop: orange
          // Destination: gray
          let statusColorClass = "text-[#8F9E97]";
          if (stop.status === "Departed" || stop.status === "Completed") {
            statusColorClass = "text-[#16A779]";
          } else if (stop.status === "Next stop") {
            statusColorClass = "text-[#F59E0B]";
          } else if (stop.status === "Destination") {
            statusColorClass = "text-[#8F9E97]";
          }

          return (
            <div
              key={stop.id}
              className={`relative flex items-start justify-between gap-4 ${
                !isLast ? "pb-6" : ""
              }`}
            >
              {/* Thin vertical line connecting markers */}
              {!isLast && (
                <span
                  className="absolute left-[5px] -translate-x-1/2 top-[14px] -bottom-1 w-[1.5px] bg-[#E5E7EB]"
                  aria-hidden="true"
                />
              )}

              {/* Stop Info: Marker and Name + Time */}
              <div className="flex items-start gap-3.5 min-w-0">
                <div className="relative z-10 mt-1 flex items-center justify-center w-2.5 h-2.5 shrink-0">
                  {markerElement}
                </div>

                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-bold text-[#193B32] leading-tight truncate">
                    {stop.name}
                  </span>
                  <span className="text-xs text-[#71877D] mt-1 leading-none">
                    {stop.time}
                  </span>
                </div>
              </div>

              {/* Far-right Status Label */}
              <span
                className={`text-sm font-medium tracking-tight text-right shrink-0 mt-0.5 ${statusColorClass}`}
              >
                {stop.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
