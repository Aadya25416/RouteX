"use client";

import React, { useState, useEffect, useCallback } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import RouteGuard from "@/components/auth/RouteGuard";
import { api, ApiError } from "@/lib/api";
import { AdminUser, AdminUserRole } from "@/types/admin";

interface BackendUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  preferred_language: string;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface UserListResponse {
  total: number;
  limit: number;
  offset: number;
  items: BackendUser[];
}

export default function UsersManagementPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("ALL");
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);

  // Add User Form state
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<AdminUserRole>("driver");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ignore = false;
    const params = new URLSearchParams();
    if (roleFilter !== "ALL") params.append("role", roleFilter);
    if (searchQuery.trim()) params.append("search", searchQuery.trim());
    params.append("limit", "100");

    const endpoint = `/api/v1/users?${params.toString()}`;
    api.get<UserListResponse>(endpoint)
      .then((data) => {
        if (!ignore && data && data.items) {
          const mapped: AdminUser[] = data.items.map((u) => ({
            id: u.id,
            name: u.full_name,
            email: u.email,
            role: u.role as AdminUserRole,
            status: u.is_active ? "Active" : "Inactive",
            createdAt: u.created_at ? u.created_at.split("T")[0] : "Recent",
            lastActive: u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : "Never",
          }));
          setUsers(mapped);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          const msg = err instanceof ApiError ? err.message : (err instanceof Error ? err.message : "Failed to load users from backend.");
          setLoadError(msg);
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [roleFilter, searchQuery, reloadKey]);

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim()) {
      setFormError("Full name and email are required.");
      return;
    }
    if (!newEmail.includes("@")) {
      setFormError("Please enter a valid email address.");
      return;
    }
    if (!newPassword || newPassword.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      await api.post<BackendUser>("/api/v1/users", {
        email: newEmail.trim(),
        full_name: newName.trim(),
        password: newPassword,
        role: newRole,
        preferred_language: "en",
      });

      setShowAddModal(false);
      setNewName("");
      setNewEmail("");
      setNewPassword("");
      setNewRole("driver");
      setActionSuccessMsg(`User ${newEmail} created successfully.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : (err instanceof Error ? err.message : "Failed to create user.");
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleStatus = async (userId: string) => {
    const target = users.find((u) => u.id === userId);
    if (!target) return;
    const newActive = target.status !== "Active";

    try {
      await api.patch<BackendUser>(`/api/v1/users/${userId}`, {
        is_active: newActive,
      });

      setUsers((prev) =>
        prev.map((u) =>
          u.id === userId
            ? { ...u, status: newActive ? "Active" : "Inactive" }
            : u
        )
      );
      if (editingUser) {
        setEditingUser({ ...editingUser, status: newActive ? "Active" : "Inactive" });
      }
      setActionSuccessMsg(`User ${target.email} ${newActive ? "activated" : "deactivated"}.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to update user status.";
      alert(msg);
    }
  };

  const handleChangeRole = async (userId: string, targetRole: AdminUserRole) => {
    try {
      await api.patch<BackendUser>(`/api/v1/users/${userId}`, {
        role: targetRole,
      });

      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: targetRole } : u))
      );
      if (editingUser) {
        setEditingUser({ ...editingUser, role: targetRole });
      }
      setActionSuccessMsg(`User role updated to ${targetRole}.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to change user role.";
      alert(msg);
    }
  };

  return (
    <RouteGuard allowedRoles={["admin"]} pageTitle="Users & Role Management">
      <AdminLayout>
        <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
          {/* Header with Title and Add User Action */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-extrabold text-[#193B32]">Users &amp; Roles</h1>
              <p className="text-xs text-[#71877D]">
                Manage driver, field officer, dispatcher, and admin accounts, roles, and operational permissions
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="rx-admin-btn-primary cursor-pointer"
            >
              <span>+ Add User</span>
            </button>
          </div>

          {actionSuccessMsg && (
            <div className="p-3 rounded-xl bg-[#DDF4E8] border border-[#B7E4CD] text-[#12432A] text-xs font-semibold flex items-center justify-between">
              <span>✓ {actionSuccessMsg}</span>
              <button
                type="button"
                onClick={() => setActionSuccessMsg(null)}
                className="text-sm font-bold"
              >
                ✕
              </button>
            </div>
          )}

          {loadError && (
            <div className="p-3 rounded-xl bg-[#FEEEEE] border border-[#FCA5A5] text-[#DC4848] text-xs font-semibold flex items-center justify-between">
              <span>⚠ {loadError}</span>
              <button
                type="button"
                onClick={() => setReloadKey((k) => k + 1)}
                className="underline font-bold"
              >
                Retry
              </button>
            </div>
          )}

          {/* Filter / Search Bar */}
          <div className="rx-admin-card p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#71877D]">Role Filter:</span>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                aria-label="Filter users by assigned role"
                className="bg-white border border-[#DCE5D8] text-xs font-semibold text-[#193B32] py-1.5 px-3 rounded-full cursor-pointer outline-none"
              >
                <option value="ALL">All Roles</option>
                <option value="admin">System Admin</option>
                <option value="dispatcher">Dispatcher</option>
                <option value="field_officer">Field Officer</option>
                <option value="driver">Driver</option>
              </select>
            </div>

            <div className="relative w-full sm:w-64">
              <input
                type="text"
                placeholder="Search users..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full py-1.5 pl-8 pr-3 text-xs bg-white border border-[#DCE5D8] rounded-full text-[#193B32] outline-none focus:border-[#16A779]"
              />
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-[#71877D]">🔍</span>
            </div>
          </div>

          {/* Users Table */}
          <div className="rx-admin-table-wrap">
            <table className="rx-admin-table" aria-label="Users and roles table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Active</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-xs text-[#71877D]">
                      Loading user accounts from RouteX backend…
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-xs text-[#71877D]">
                      No user accounts found matching current filters.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => {
                    let roleLabel = "Driver";
                    if (u.role === "admin") roleLabel = "Admin";
                    else if (u.role === "dispatcher") roleLabel = "Dispatcher";
                    else if (u.role === "field_officer") roleLabel = "Field Officer";

                    return (
                      <tr key={u.id}>
                        <td>
                          <div className="flex items-center gap-2.5">
                            <span className="w-7 h-7 rounded-full bg-[#FAFBF7] border border-[#DCE5D8] flex items-center justify-center font-bold text-xs text-[#193B32]">
                              {u.name.charAt(0)}
                            </span>
                            <span className="font-bold text-[#193B32]">{u.name}</span>
                          </div>
                        </td>
                        <td className="font-mono text-xs text-[#71877D]">{u.email}</td>
                        <td>
                          <span className="font-semibold text-xs text-[#193B32]">{roleLabel}</span>
                        </td>
                        <td>
                          <span
                            className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                              u.status === "Active"
                                ? "bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD]"
                                : "bg-[#FEEEEE] text-[#DC4848] border border-[#FCA5A5]"
                            }`}
                          >
                            {u.status}
                          </span>
                        </td>
                        <td className="text-xs text-[#71877D]">{u.lastActive}</td>
                        <td className="text-right">
                          <button
                            type="button"
                            onClick={() => setEditingUser(u)}
                            className="px-2.5 py-1 text-xs font-bold text-[#176B4D] hover:bg-[#FAFBF7] rounded-lg border border-[#DCE5D8] transition-colors cursor-pointer"
                          >
                            Manage
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Add User Modal */}
          {showAddModal && (
            <div
              role="dialog"
              aria-modal="true"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
            >
              <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl border border-[#DCE5D8]">
                <div className="flex items-center justify-between pb-3 mb-4 border-b border-[#E8EFE5]">
                  <h3 className="font-bold text-[#193B32] text-sm">Add New User</h3>
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="text-[#71877D] hover:text-[#193B32] text-lg font-bold"
                  >
                    ✕
                  </button>
                </div>

                {formError && (
                  <div className="p-2.5 mb-3 rounded-lg bg-[#FEEEEE] border border-[#FCA5A5] text-[#DC4848] text-xs">
                    {formError}
                  </div>
                )}

                <form onSubmit={handleAddUser} className="space-y-3.5 text-xs">
                  <div>
                    <label htmlFor="user-fullname" className="block font-bold text-[#193B32] mb-1">
                      Full Name
                    </label>
                    <input
                      id="user-fullname"
                      type="text"
                      required
                      placeholder="e.g. Rahul Sen"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      className="w-full p-2.5 bg-white border border-[#DCE5D8] rounded-xl outline-none focus:border-[#16A779] text-[#193B32]"
                    />
                  </div>

                  <div>
                    <label htmlFor="user-email-addr" className="block font-bold text-[#193B32] mb-1">
                      Email Address
                    </label>
                    <input
                      id="user-email-addr"
                      type="email"
                      required
                      placeholder="e.g. rahul@routex.in"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      className="w-full p-2.5 bg-white border border-[#DCE5D8] rounded-xl outline-none focus:border-[#16A779] text-[#193B32]"
                    />
                  </div>

                  <div>
                    <label htmlFor="user-password" className="block font-bold text-[#193B32] mb-1">
                      Initial Password (min 8 chars)
                    </label>
                    <input
                      id="user-password"
                      type="password"
                      required
                      placeholder="Enter secure initial password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full p-2.5 bg-white border border-[#DCE5D8] rounded-xl outline-none focus:border-[#16A779] text-[#193B32]"
                    />
                  </div>

                  <div>
                    <label htmlFor="user-assigned-role" className="block font-bold text-[#193B32] mb-1">
                      Assigned Role
                    </label>
                    <select
                      id="user-assigned-role"
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value as AdminUserRole)}
                      className="w-full p-2.5 bg-white border border-[#DCE5D8] rounded-xl outline-none focus:border-[#16A779] text-[#193B32] font-semibold"
                    >
                      <option value="driver">Driver (View routes, submit evidence)</option>
                      <option value="field_officer">Field Officer (Submit road incidents &amp; evidence)</option>
                      <option value="dispatcher">Dispatcher (Route planning, incident triage, deliveries)</option>
                      <option value="admin">System Admin (Full system configuration &amp; user management)</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E8EFE5]">
                    <button
                      type="button"
                      onClick={() => setShowAddModal(false)}
                      className="px-4 py-2 border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32]"
                      disabled={isSubmitting}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="px-4 py-2 bg-[#12432A] text-white rounded-full text-xs font-bold hover:bg-[#0b2f1c] disabled:opacity-50"
                    >
                      {isSubmitting ? "Creating…" : "Create User"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Manage User Modal */}
          {editingUser && (
            <div
              role="dialog"
              aria-modal="true"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
            >
              <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl border border-[#DCE5D8]">
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E8EFE5]">
                  <h3 className="font-bold text-[#193B32] text-sm">Manage Account: {editingUser.name}</h3>
                  <button
                    type="button"
                    onClick={() => setEditingUser(null)}
                    className="text-[#71877D] hover:text-[#193B32] text-lg font-bold"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3 text-xs mb-4">
                  <p className="text-[#71877D]">
                    Current Status: <strong className="text-[#193B32]">{editingUser.status}</strong>
                  </p>
                  <div>
                    <label htmlFor="change-role-select" className="block font-bold text-[#193B32] mb-1">
                      Change Role
                    </label>
                    <select
                      id="change-role-select"
                      defaultValue={editingUser.role}
                      onChange={(e) => handleChangeRole(editingUser.id, e.target.value as AdminUserRole)}
                      className="w-full p-2 bg-white border border-[#DCE5D8] rounded-xl text-xs font-semibold"
                    >
                      <option value="driver">Driver</option>
                      <option value="field_officer">Field Officer</option>
                      <option value="dispatcher">Dispatcher</option>
                      <option value="admin">System Admin</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-[#E8EFE5]">
                  <button
                    type="button"
                    onClick={() => handleToggleStatus(editingUser.id)}
                    className={`px-3 py-1.5 rounded-full text-xs font-bold cursor-pointer ${
                      editingUser.status === "Active"
                        ? "bg-[#FEEEEE] text-[#DC4848] border border-[#FCA5A5]"
                        : "bg-[#DDF4E8] text-[#12432A] border border-[#B7E4CD]"
                    }`}
                  >
                    {editingUser.status === "Active" ? "Deactivate Account" : "Activate Account"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingUser(null)}
                    className="px-3 py-1.5 border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32] cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </AdminLayout>
    </RouteGuard>
  );
}
