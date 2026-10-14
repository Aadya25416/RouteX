"use client";

import React from "react";
import DriverSidebar from "./DriverSidebar";
import DriverTopbar from "./DriverTopbar";
import DriverFooter from "./DriverFooter";
import "@/app/driver/driver.css";

import RouteGuard from "@/components/auth/RouteGuard";

interface DriverLayoutProps {
  children: React.ReactNode;
}

export default function DriverLayout({ children }: DriverLayoutProps) {
  return (
    <RouteGuard
      allowedRoles={["driver", "dispatcher", "admin"]}
      pageTitle="Driver Logistics Portal"
    >
      <div className="rx-driver-root">
        <DriverSidebar />
        <div className="rx-driver-main">
          <DriverTopbar />
          <main className="rx-driver-page">{children}</main>
          <DriverFooter />
        </div>
      </div>
    </RouteGuard>
  );
}
