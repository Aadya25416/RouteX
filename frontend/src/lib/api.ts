/**
 * Central API Client for RouteX
 * Handles JWT access tokens, credentials for HttpOnly refresh cookies,
 * request queuing during token refresh, and normalized error handling.
 */

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  skipAuth?: boolean;
  skipRefreshRetry?: boolean;
}

let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;
let onAuthFailureCallback: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setOnAuthFailure(callback: (() => void) | null): void {
  onAuthFailureCallback = callback;
}

/**
 * Initiates single-flight token refresh using the HttpOnly cookie.
 * Prevents concurrent refresh storms and returns the new access token.
 */
async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });

      if (!res.ok) {
        setAccessToken(null);
        if (onAuthFailureCallback) {
          onAuthFailureCallback();
        }
        return null;
      }

      const data = await res.json();
      if (data && data.access_token) {
        setAccessToken(data.access_token);
        return data.access_token as string;
      }

      setAccessToken(null);
      return null;
    } catch {
      setAccessToken(null);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Central fetch wrapper with Bearer token injection, credentials inclusion,
 * JSON serialization, and single-attempt 401 refresh-and-retry.
 */
export async function apiClient<T = unknown>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    body,
    headers: customHeaders = {},
    skipAuth = false,
    skipRefreshRetry = false,
    ...fetchOpts
  } = options;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(customHeaders as Record<string, string>),
  };

  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (!isFormData && body !== undefined && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (!skipAuth && inMemoryAccessToken) {
    headers["Authorization"] = `Bearer ${inMemoryAccessToken}`;
  }

  const isAuthRoute =
    endpoint.includes("/api/v1/auth/login") ||
    endpoint.includes("/api/v1/auth/refresh") ||
    endpoint.includes("/api/v1/auth/logout");

  const serializedBody =
    isFormData || body === undefined
      ? (body as BodyInit | undefined)
      : JSON.stringify(body);

  let response: Response;
  try {
    response = await fetch(endpoint, {
      ...fetchOpts,
      headers,
      body: serializedBody,
      credentials: "include", // Ensure HttpOnly cookies are attached
    });
  } catch (networkErr: unknown) {
    const msg =
      networkErr instanceof Error ? networkErr.message : "Network request failed.";
    throw new ApiError(0, `Network error connecting to RouteX API: ${msg}`);
  }

  // Handle 401 Unauthorized for eligible requests (not auth routes, not already retried)
  if (response.status === 401 && !skipRefreshRetry && !isAuthRoute) {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      // Retry once with new token
      return apiClient<T>(endpoint, {
        ...options,
        skipRefreshRetry: true,
      });
    }
  }

  // Parse response
  let responseData: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      responseData = await response.json();
    } catch {
      responseData = null;
    }
  } else {
    try {
      responseData = await response.text();
    } catch {
      responseData = null;
    }
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    if (responseData && typeof responseData === "object" && "detail" in responseData) {
      const detail = (responseData as { detail: unknown }).detail;
      errorDetail =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ")
          : JSON.stringify(detail);
    }
    throw new ApiError(response.status, errorDetail, responseData);
  }

  return responseData as T;
}

export const api = {
  get: <T = unknown>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "GET" }),

  post: <T = unknown>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "POST", body }),

  patch: <T = unknown>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "PATCH", body }),

  delete: <T = unknown>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "DELETE" }),

  upload: <T = unknown>(endpoint: string, formData: FormData, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "POST", body: formData }),

  refresh: refreshAccessToken,
};
