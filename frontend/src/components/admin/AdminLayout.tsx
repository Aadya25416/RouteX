"use client";

import React from "react";
import AdminSidebar from "./AdminSidebar";
import AdminTopbar from "./AdminTopbar";
import AdminFooter from "./AdminFooter";
import "@/app/admin/admin.css";

import RouteGuard from "@/components/auth/RouteGuard";

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <RouteGuard
      allowedRoles={["admin", "dispatcher", "field_officer"]}
      pageTitle="Operations & Admin Portal"
    >
      <div className="rx-admin-root">
        <AdminSidebar />
        <div className="rx-admin-main">
          <AdminTopbar />
          <main className="rx-admin-page">{children}</main>
          <AdminFooter />
        </div>
      </div>
    </RouteGuard>
  );
}
