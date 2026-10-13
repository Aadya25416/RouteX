"use client";

import React, { useState } from "react";
import AdminLayout from "@/components/admin/AdminLayout";
import { INITIAL_ADMIN_USERS } from "@/data/adminData";
import { AdminUser, AdminUserRole } from "@/types/admin";

export default function UsersManagementPage() {
  const [users, setUsers] = useState<AdminUser[]>(INITIAL_ADMIN_USERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("ALL");
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);

  // Add User Form state
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<AdminUserRole>("driver");
  const [formError, setFormError] = useState<string | null>(null);

  const filteredUsers = users.filter((u) => {
    if (roleFilter !== "ALL" && u.role !== roleFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = u.name.toLowerCase().includes(q);
      const matchEmail = u.email.toLowerCase().includes(q);
      if (!matchName && !matchEmail) return false;
    }
    return true;
  });

  const handleAddUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim()) {
      setFormError("Full name and email are required.");
      return;
    }
    if (!newEmail.includes("@")) {
      setFormError("Please enter a valid email address.");
      return;
    }

    const newUser: AdminUser = {
      id: `usr-${Date.now().toString().slice(-4)}`,
      name: newName,
      email: newEmail,
      role: newRole,
      status: "Active",
      createdAt: new Date().toISOString().split("T")[0],
      lastActive: "Just now",
    };

    setUsers([newUser, ...users]);
    setShowAddModal(false);
    setNewName("");
    setNewEmail("");
    setNewRole("driver");
    setFormError(null);
  };

  const handleToggleStatus = (userId: string) => {
    setUsers((prev) =>
      prev.map((u) =>
        u.id === userId
          ? { ...u, status: u.status === "Active" ? "Inactive" : "Active" }
          : u
      )
    );
    if (editingUser) setEditingUser(null);
  };

  const handleChangeRole = (userId: string, targetRole: AdminUserRole) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, role: targetRole } : u))
    );
    if (editingUser) setEditingUser(null);
  };

  return (
    <AdminLayout>
      <div className="flex flex-col gap-5 max-w-7xl mx-auto w-full">
        {/* Header with Title and Add User Action */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-[#193B32]">Users &amp; Roles</h1>
            <p className="text-xs text-[#71877D]">
              Manage driver, field officer, and admin accounts, roles, and operational permissions
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
              {filteredUsers.map((u) => {
                let roleLabel = "Driver";
                if (u.role === "admin") roleLabel = "Admin";
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
              })}
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
                  <label htmlFor="user-assigned-role" className="block font-bold text-[#193B32] mb-1">
                    Assigned Role
                  </label>
                  <select
                    id="user-assigned-role"
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value as AdminUserRole)}
                    className="w-full p-2.5 bg-white border border-[#DCE5D8] rounded-xl outline-none focus:border-[#16A779] text-[#193B32] font-semibold"
                  >
                    <option value="driver">Driver (View routes, submit field reports)</option>
                    <option value="field_officer">Field Officer (Monitor corridor, review hazards)</option>
                    <option value="admin">System Admin (Full system configuration)</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#E8EFE5]">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-[#12432A] text-white rounded-full text-xs font-bold hover:bg-[#0b2f1c]"
                  >
                    Create User
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
                    <option value="admin">System Admin</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[#E8EFE5]">
                <button
                  type="button"
                  onClick={() => handleToggleStatus(editingUser.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-bold ${
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
                  className="px-3 py-1.5 border border-[#DCE5D8] rounded-full text-xs font-semibold text-[#193B32]"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
