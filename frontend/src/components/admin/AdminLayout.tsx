"use client";

import React from "react";
import AdminSidebar from "./AdminSidebar";
import AdminTopbar from "./AdminTopbar";
import AdminFooter from "./AdminFooter";
import "@/app/admin/admin.css";

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <div className="rx-admin-root">
      <AdminSidebar />
      <div className="rx-admin-main">
        <AdminTopbar />
        <main className="rx-admin-page">{children}</main>
        <AdminFooter />
      </div>
    </div>
  );
}
