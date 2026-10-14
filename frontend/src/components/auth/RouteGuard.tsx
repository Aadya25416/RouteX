"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, UserRole } from "@/context/AuthContext";

interface RouteGuardProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
  pageTitle?: string;
}

export default function RouteGuard({
  allowedRoles,
  children,
  pageTitle = "Protected Portal",
}: RouteGuardProps) {
  const router = useRouter();
  const { user, isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  // Loading state — render clean spinner without redirecting
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] w-full gap-4 p-8">
        <div className="w-9 h-9 border-3 border-[#16A779] border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-semibold text-[#71877D]">
          Verifying security credentials…
        </p>
      </div>
    );
  }

  // Unauthenticated — will be redirected by useEffect
  if (!isAuthenticated || !user) {
    return null;
  }

  // Authenticated but unauthorized for this specific role/page
  if (!allowedRoles.includes(user.role)) {
    const homeTarget = user.role === "driver" ? "/driver" : "/admin";

    return (
      <div className="flex items-center justify-center min-h-[70vh] p-6">
        <div className="bg-white border border-[#DCE5D8] rounded-2xl p-8 max-w-md w-full shadow-lg text-center">
          <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-[#FEEEEE] text-[#DC4848] flex items-center justify-center text-2xl font-bold">
            ⚠
          </div>
          <h2 className="text-lg font-extrabold text-[#193B32] mb-1">
            Access Restricted (403)
          </h2>
          <p className="text-xs text-[#71877D] mb-4">
            Your account ({user.email}) has role{" "}
            <span className="font-bold text-[#193B32] bg-[#EAF2E7] px-2 py-0.5 rounded">
              {user.role}
            </span>
            , which does not have permission to access {pageTitle}.
          </p>
          <div className="flex flex-col gap-2">
            <Link
              href={homeTarget}
              className="py-2.5 px-4 bg-[#12432A] text-white rounded-full text-xs font-semibold hover:bg-[#0d3420] transition-colors"
            >
              Return to Authorized Dashboard →
            </Link>
            <Link
              href="/login"
              className="py-2 px-4 text-[#71877D] hover:text-[#193B32] text-xs font-medium"
            >
              Switch Account
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
