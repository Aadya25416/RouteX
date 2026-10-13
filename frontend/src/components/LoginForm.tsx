"use client";

import React, { useState } from "react";

interface FormState {
  email: string;
  password: string;
  showPassword: boolean;
  isLoading: boolean;
  error: string | null;
}

export default function LoginForm() {
  // NOTE: router.push("/map") is reserved for the post-authentication redirect.
  // Uncomment import { useRouter } from "next/navigation" when backend auth is wired.
  const [form, setForm] = useState<FormState>({
    email: "",
    password: "",
    showPassword: false,
    isLoading: false,
    error: null,
  });

  const [fieldErrors, setFieldErrors] = useState<{
    email?: string;
    password?: string;
  }>({});

  const validate = (): boolean => {
    const errs: { email?: string; password?: string } = {};
    if (!form.email.trim()) {
      errs.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      errs.email = "Enter a valid email address.";
    }
    if (!form.password) {
      errs.password = "Password is required.";
    } else if (form.password.length < 6) {
      errs.password = "Password must be at least 6 characters.";
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setForm((f) => ({ ...f, isLoading: true, error: null }));

    try {
      // NOTE: The RouteX backend does not currently expose an authentication
      // endpoint (/api/v1/auth/login or similar). The UI is fully built and
      // integration-ready. Once the backend exposes an auth contract, replace
      // this block with a real fetch call using the documented payload schema.
      //
      // Example integration point:
      //   const res = await fetch("/api/v1/auth/login", {
      //     method: "POST",
      //     headers: { "Content-Type": "application/json" },
      //     body: JSON.stringify({ email: form.email, password: form.password }),
      //   });
      //   if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
      //   const { access_token } = await res.json();
      //   // store token and redirect
      //   router.push("/map");

      // For now: simulate latency and surface honest status
      await new Promise((r) => setTimeout(r, 800));
      throw new Error(
        "Authentication endpoint not yet available. The RouteX backend does not expose a /api/v1/auth/login route in its current Phase 1 implementation. Please start the backend and check /docs for available endpoints."
      );
    } catch (err: unknown) {
      setForm((f) => ({
        ...f,
        isLoading: false,
        error: err instanceof Error ? err.message : "Login failed.",
      }));
    }
  };

  const updateField =
    (field: keyof Pick<FormState, "email" | "password">) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((f) => ({ ...f, [field]: e.target.value }));
      if (fieldErrors[field]) {
        setFieldErrors((fe) => ({ ...fe, [field]: undefined }));
      }
      if (form.error) {
        setForm((f) => ({ ...f, error: null }));
      }
    };

  return (
    <form
      id="login-form"
      className="login-form"
      onSubmit={handleSubmit}
      noValidate
      aria-label="RouteX login form"
    >
      {/* Email */}
      <div className="login-field-group">
        <label htmlFor="login-email" className="login-label">
          Email address
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="email"
          className={`login-input ${fieldErrors.email ? "login-input-error" : ""}`}
          placeholder="you@example.com"
          value={form.email}
          onChange={updateField("email")}
          aria-invalid={!!fieldErrors.email}
          aria-describedby={fieldErrors.email ? "login-email-err" : undefined}
          disabled={form.isLoading}
        />
        {fieldErrors.email && (
          <span id="login-email-err" className="login-field-error" role="alert">
            {fieldErrors.email}
          </span>
        )}
      </div>

      {/* Password */}
      <div className="login-field-group">
        <label htmlFor="login-password" className="login-label">
          Password
        </label>
        <div className="login-password-wrapper">
          <input
            id="login-password"
            type={form.showPassword ? "text" : "password"}
            autoComplete="current-password"
            className={`login-input login-input-password ${fieldErrors.password ? "login-input-error" : ""}`}
            placeholder="••••••••"
            value={form.password}
            onChange={updateField("password")}
            aria-invalid={!!fieldErrors.password}
            aria-describedby={
              fieldErrors.password ? "login-password-err" : undefined
            }
            disabled={form.isLoading}
          />
          <button
            type="button"
            className="login-show-password"
            onClick={() =>
              setForm((f) => ({ ...f, showPassword: !f.showPassword }))
            }
            aria-label={form.showPassword ? "Hide password" : "Show password"}
            disabled={form.isLoading}
          >
            {form.showPassword ? (
              <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
            ) : (
              <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            )}
          </button>
        </div>
        {fieldErrors.password && (
          <span
            id="login-password-err"
            className="login-field-error"
            role="alert"
          >
            {fieldErrors.password}
          </span>
        )}
      </div>

      {/* Auth unavailability notice */}
      <div className="login-auth-notice" role="note">
        <span className="login-auth-notice-icon" aria-hidden="true">ℹ️</span>
        <span>
          Authentication is <strong>UI-ready</strong>. Backend auth endpoint
          integration pending Phase 2 backend implementation.
        </span>
      </div>

      {/* Error state */}
      {form.error && (
        <div className="login-error" role="alert" aria-live="assertive">
          <span aria-hidden="true">⚠️</span>
          <span>{form.error}</span>
        </div>
      )}

      {/* Submit */}
      <button
        id="login-submit-btn"
        type="submit"
        className="login-submit-btn"
        disabled={form.isLoading}
        aria-busy={form.isLoading}
      >
        {form.isLoading ? (
          <>
            <span className="login-spinner" aria-hidden="true" />
            <span>Signing in…</span>
          </>
        ) : (
          <span>Sign In</span>
        )}
      </button>
    </form>
  );
}
