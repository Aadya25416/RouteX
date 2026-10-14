"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api, setAccessToken, setOnAuthFailure, ApiError } from "@/lib/api";

export type UserRole = "admin" | "dispatcher" | "field_officer" | "driver" | "ml_service";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  preferred_language: string;
  is_active: boolean;
  last_login_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string | null;
  user: UserProfile;
}

interface AuthContextValue {
  user: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<UserProfile>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<UserProfile | null>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setIsLoading(false);
  }, []);

  const refreshProfile = useCallback(async (): Promise<UserProfile | null> => {
    try {
      const profile = await api.get<UserProfile>("/api/v1/auth/me");
      setUser(profile);
      return profile;
    } catch {
      clearSession();
      return null;
    }
  }, [clearSession]);

  // Initial session restoration on mount
  useEffect(() => {
    let isMounted = true;

    setOnAuthFailure(() => {
      if (isMounted) {
        clearSession();
      }
    });

    const initAuth = async () => {
      try {
        // Attempt to refresh session with HttpOnly cookie
        const token = await api.refresh();
        if (token && isMounted) {
          const profile = await api.get<UserProfile>("/api/v1/auth/me");
          if (isMounted) {
            setUser(profile);
          }
        } else if (isMounted) {
          clearSession();
        }
      } catch {
        if (isMounted) {
          clearSession();
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    initAuth();

    return () => {
      isMounted = false;
      setOnAuthFailure(null);
    };
  }, [clearSession]);

  const login = useCallback(
    async (usernameOrEmail: string, password: string): Promise<UserProfile> => {
      setIsLoading(true);
      try {
        const res = await api.post<LoginResponse>("/api/v1/auth/login", {
          username_or_email: usernameOrEmail.trim(),
          password,
        });

        if (!res || !res.access_token || !res.user) {
          throw new ApiError(500, "Invalid authentication response structure.");
        }

        setAccessToken(res.access_token);
        setUser(res.user);
        setIsLoading(false);
        return res.user;
      } catch (err) {
        clearSession();
        throw err;
      }
    },
    [clearSession]
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await api.post("/api/v1/auth/logout");
    } catch {
      // Proceed with local teardown even if server logout request fails
    } finally {
      clearSession();
      router.push("/login");
    }
  }, [clearSession, router]);

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
