"use client";

import React, { useState, useId } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import HomeFooter from "@/components/home/HomeFooter";
import "./Login.css";

// MapLibre requires a browser DOM — disable SSR
const LoginMapBackground = dynamic(
  () => import("@/components/login/LoginMapBackground"),
  {
    ssr: false,
    loading: () => (
      <div
        className="rx-login-map-bg"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: "100vw",
          height: "100vh",
          backgroundColor: "#EAF2E7",
          zIndex: 0,
          pointerEvents: "none",
        }}
        aria-hidden="true"
      />
    ),
  }
);

type Tab = "login" | "signup";
type Role = "field_officer" | "driver";

interface LoginState {
  email: string;
  password: string;
  showPassword: boolean;
  remember: boolean;
  isLoading: boolean;
  error: string | null;
}

interface SignupState {
  fullName: string;
  email: string;
  password: string;
  confirm: string;
  showPassword: boolean;
  showConfirm: boolean;
  isLoading: boolean;
  error: string | null;
}

interface FieldErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirm?: string;
}

function IconMail() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function IconUser() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="8" r="5" />
      <path d="M20 21a8 8 0 1 0-16 0" />
    </svg>
  );
}

function IconEye({ off }: { off?: boolean }) {
  return off ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconHome() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function IconOfficer() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

function IconTruck() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="1" y="3" width="15" height="13" rx="1" />
      <path d="M16 8h4l3 3v5h-7V8z" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  );
}

function SidePanel() {
  return (
    <aside className="rx-side-panel" aria-label="Route summary">
      <div className="rx-side-time">25 min</div>
      <div className="rx-side-route-line">
        <svg width="100%" height="28" viewBox="0 0 188 28" fill="none" aria-hidden="true">
          <circle cx="10" cy="14" r="5" fill="#16A779" />
          <line x1="15" y1="14" x2="173" y2="14" stroke="#16A779" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="178" cy="14" r="5" fill="#16A779" />
        </svg>
      </div>
      <div>
        <div className="rx-side-panel-label">Safer Routes</div>
        <div className="rx-side-panel-label">Stronger Connections</div>
      </div>
      <div className="rx-side-panel-sub">AI-powered route intelligence for the Guwahati–Tawang corridor.</div>
      <div className="rx-side-demo-tag">Corridor Intelligence Active</div>
    </aside>
  );
}

function LoginFormInner({ role, onSwitchTab }: { role: Role; onSwitchTab: () => void }) {
  const router = useRouter();
  const { login } = useAuth();
  const emailId = useId();
  const pwId = useId();
  const [state, setState] = useState<LoginState>({
    email: "",
    password: "",
    showPassword: false,
    remember: false,
    isLoading: false,
    error: null,
  });
  const [errs, setErrs] = useState<FieldErrors>({});
  const [forgotMsg, setForgotMsg] = useState<string | null>(null);

  const validate = () => {
    const e: FieldErrors = {};
    if (!state.email.trim()) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.email)) e.email = "Enter a valid email.";
    if (!state.password) e.password = "Password is required.";
    else if (state.password.length < 6) e.password = "At least 6 characters required.";
    setErrs(e);
    return Object.keys(e).length === 0;
  };

  const upd = (f: "email" | "password") => (ev: React.ChangeEvent<HTMLInputElement>) => {
    setState((s) => ({ ...s, [f]: ev.target.value, error: null }));
    if (errs[f]) setErrs((e) => ({ ...e, [f]: undefined }));
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setForgotMsg(null);
    if (!validate()) return;
    setState((s) => ({ ...s, isLoading: true, error: null }));

    try {
      const user = await login(state.email, state.password);
      if (user.role === "driver") {
        router.push("/driver");
      } else {
        router.push("/admin");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed.";
      setState((s) => ({ ...s, isLoading: false, error: msg }));
    }
  };

  return (
    <form id="login-form" onSubmit={handleSubmit} noValidate aria-label="Login form">
      <div className="rx-field">
        <label htmlFor={emailId} className="rx-field-label">
          Email address
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconMail />
          </span>
          <input
            id={emailId}
            type="email"
            autoComplete="email"
            placeholder="Enter your email"
            value={state.email}
            onChange={upd("email")}
            disabled={state.isLoading}
            aria-invalid={!!errs.email}
            className={`rx-input${errs.email ? " rx-input--error" : ""}`}
          />
        </div>
        {errs.email && (
          <span className="rx-field-err" role="alert">
            {errs.email}
          </span>
        )}
      </div>

      <div className="rx-field">
        <label htmlFor={pwId} className="rx-field-label">
          Password
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconLock />
          </span>
          <input
            id={pwId}
            type={state.showPassword ? "text" : "password"}
            autoComplete="current-password"
            placeholder="Enter your password"
            value={state.password}
            onChange={upd("password")}
            disabled={state.isLoading}
            aria-invalid={!!errs.password}
            className={`rx-input rx-input--pw${errs.password ? " rx-input--error" : ""}`}
          />
          <button
            type="button"
            className="rx-pw-toggle"
            onClick={() => setState((s) => ({ ...s, showPassword: !s.showPassword }))}
            aria-label={state.showPassword ? "Hide password" : "Show password"}
          >
            <IconEye off={state.showPassword} />
          </button>
        </div>
        {errs.password && (
          <span className="rx-field-err" role="alert">
            {errs.password}
          </span>
        )}
      </div>

      <div className="rx-remember-row">
        <label className="rx-remember-label">
          <input
            type="checkbox"
            className="rx-checkbox"
            checked={state.remember}
            onChange={(e) => setState((s) => ({ ...s, remember: e.target.checked }))}
          />
          Remember me
        </label>
        <button
          type="button"
          className="rx-forgot-link"
          onClick={() =>
            setForgotMsg(
              "Password recovery requires administrative authorization. Please contact your RouteX operations administrator for credential assistance."
            )
          }
        >
          Forgot password?
        </button>
      </div>

      {forgotMsg && (
        <div className="rx-info-banner" role="status">
          <span>ℹ</span>
          <span>{forgotMsg}</span>
        </div>
      )}

      {state.error && (
        <div className="rx-err-banner" role="alert">
          <span>⚠</span>
          <span>{state.error}</span>
        </div>
      )}

      <button
        id="login-submit-btn"
        type="submit"
        className="rx-primary-btn"
        disabled={state.isLoading}
        aria-busy={state.isLoading}
      >
        {state.isLoading ? (
          <>
            <span className="rx-spinner" />
            <span>Signing in…</span>
          </>
        ) : (
          <span>Sign In →</span>
        )}
      </button>

      <div className="rx-or-divider">OR</div>
      <button type="button" className="rx-secondary-btn" onClick={onSwitchTab}>
        Create a new account
      </button>
      <input type="hidden" name="role" value={role} />
    </form>
  );
}

function SignupFormInner({ onSwitchTab }: { onSwitchTab: () => void }) {
  const router = useRouter();
  const { login } = useAuth();
  const nameId = useId();
  const emailId = useId();
  const pwId = useId();
  const confirmId = useId();
  const [state, setState] = useState<SignupState>({
    fullName: "",
    email: "",
    password: "",
    confirm: "",
    showPassword: false,
    showConfirm: false,
    isLoading: false,
    error: null,
  });
  const [errs, setErrs] = useState<FieldErrors>({});

  const validate = () => {
    const e: FieldErrors = {};
    if (!state.fullName.trim()) e.fullName = "Full name is required.";
    if (!state.email.trim()) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.email)) e.email = "Enter a valid email.";
    if (!state.password) e.password = "Password is required.";
    else if (state.password.length < 6) e.password = "At least 6 characters required.";
    if (!state.confirm) e.confirm = "Please confirm your password.";
    else if (state.confirm !== state.password) e.confirm = "Passwords do not match.";
    setErrs(e);
    return Object.keys(e).length === 0;
  };

  const upd =
    (f: keyof Pick<SignupState, "fullName" | "email" | "password" | "confirm">) =>
    (ev: React.ChangeEvent<HTMLInputElement>) => {
      setState((s) => ({ ...s, [f]: ev.target.value, error: null }));
      if (errs[f]) setErrs((e) => ({ ...e, [f]: undefined }));
    };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setState((s) => ({ ...s, isLoading: true, error: null }));

    try {
      // 1. Driver self-registration via existing central API client
      await api.post("/api/v1/auth/register", {
        full_name: state.fullName.trim(),
        email: state.email.trim(),
        password: state.password,
      });

      // 2. Immediate login with issued credentials
      const user = await login(state.email.trim(), state.password);
      if (user.role === "driver") {
        router.push("/driver");
      } else {
        router.push("/admin");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed.";
      setState((s) => ({ ...s, isLoading: false, error: msg }));
    }
  };

  return (
    <form id="signup-form" onSubmit={handleSubmit} noValidate aria-label="Sign up form">
      <div className="rx-field">
        <label htmlFor={nameId} className="rx-field-label">
          Full name
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconUser />
          </span>
          <input
            id={nameId}
            type="text"
            autoComplete="name"
            placeholder="Your full name"
            value={state.fullName}
            onChange={upd("fullName")}
            disabled={state.isLoading}
            aria-invalid={!!errs.fullName}
            className={`rx-input${errs.fullName ? " rx-input--error" : ""}`}
          />
        </div>
        {errs.fullName && (
          <span className="rx-field-err" role="alert">
            {errs.fullName}
          </span>
        )}
      </div>

      <div className="rx-field">
        <label htmlFor={emailId} className="rx-field-label">
          Email address
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconMail />
          </span>
          <input
            id={emailId}
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={state.email}
            onChange={upd("email")}
            disabled={state.isLoading}
            aria-invalid={!!errs.email}
            className={`rx-input${errs.email ? " rx-input--error" : ""}`}
          />
        </div>
        {errs.email && (
          <span className="rx-field-err" role="alert">
            {errs.email}
          </span>
        )}
      </div>

      <div className="rx-field">
        <label htmlFor={pwId} className="rx-field-label">
          Password
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconLock />
          </span>
          <input
            id={pwId}
            type={state.showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Create a password"
            value={state.password}
            onChange={upd("password")}
            disabled={state.isLoading}
            aria-invalid={!!errs.password}
            className={`rx-input rx-input--pw${errs.password ? " rx-input--error" : ""}`}
          />
          <button
            type="button"
            className="rx-pw-toggle"
            onClick={() => setState((s) => ({ ...s, showPassword: !s.showPassword }))}
            aria-label={state.showPassword ? "Hide" : "Show"}
          >
            <IconEye off={state.showPassword} />
          </button>
        </div>
        {errs.password && (
          <span className="rx-field-err" role="alert">
            {errs.password}
          </span>
        )}
      </div>

      <div className="rx-field">
        <label htmlFor={confirmId} className="rx-field-label">
          Confirm password
        </label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon">
            <IconLock />
          </span>
          <input
            id={confirmId}
            type={state.showConfirm ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Repeat your password"
            value={state.confirm}
            onChange={upd("confirm")}
            disabled={state.isLoading}
            aria-invalid={!!errs.confirm}
            className={`rx-input rx-input--pw${errs.confirm ? " rx-input--error" : ""}`}
          />
          <button
            type="button"
            className="rx-pw-toggle"
            onClick={() => setState((s) => ({ ...s, showConfirm: !s.showConfirm }))}
            aria-label={state.showConfirm ? "Hide" : "Show"}
          >
            <IconEye off={state.showConfirm} />
          </button>
        </div>
        {errs.confirm && (
          <span className="rx-field-err" role="alert">
            {errs.confirm}
          </span>
        )}
      </div>

      {state.error && (
        <div className="rx-err-banner" role="alert">
          <span>⚠</span>
          <span>{state.error}</span>
        </div>
      )}

      <p className="rx-terms-text">
        RouteX operates an authorized enterprise transport intelligence network. Role-based accounts are governed by platform security policies.
      </p>

      <button
        id="signup-submit-btn"
        type="submit"
        className="rx-primary-btn"
        disabled={state.isLoading}
        aria-busy={state.isLoading}
      >
        {state.isLoading ? (
          <>
            <span className="rx-spinner" />
            <span>Creating account…</span>
          </>
        ) : (
          <span>Create Account →</span>
        )}
      </button>

      <input type="hidden" name="role" value="driver" />
      <div className="rx-signin-link-row">
        Already have an account? <button type="button" onClick={onSwitchTab}>Sign in</button>
      </div>
    </form>
  );
}

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("login");
  const [role, setRole] = useState<Role>("field_officer");

  return (
    <div className="rx-login-root">
      <LoginMapBackground />
      <header className="rx-login-header">
        <Link href="/home" className="rx-login-header-home" id="header-home-btn">
          <IconHome /> Home
        </Link>
        <Link href="/home" className="rx-login-header-logo" aria-label="RouteX">
          <span className="rx-logo-route">Route</span><span className="rx-logo-x">X</span>
        </Link>
        <div style={{ width: "68px" }} aria-hidden="true" />
      </header>

      <main className="rx-login-body" id="login-main">
        <section className="rx-auth-card" aria-label="Authentication">
          <div className="rx-card-brand-header">
            <span className="rx-card-brand-wordmark">
              <span className="rx-logo-route">Route</span><span className="rx-logo-x">X</span>
            </span>
          </div>

          <div className="rx-tab-row" role="tablist" aria-label="Authentication mode">
            <button
              id="tab-login"
              role="tab"
              className="rx-tab-btn"
              aria-selected={tab === "login"}
              onClick={() => setTab("login")}
            >
              Login
            </button>
            <button
              id="tab-signup"
              role="tab"
              className="rx-tab-btn"
              aria-selected={tab === "signup"}
              onClick={() => {
                setTab("signup");
                setRole("driver");
              }}
            >
              Sign Up
            </button>
          </div>

          <h1 className="rx-card-title">{tab === "login" ? "Welcome back" : "Create your account"}</h1>
          {tab === "signup" && (
            <p className="rx-card-sub">
              Join RouteX as an authorized driver for corridor operations.
            </p>
          )}

          {tab === "login" ? (
            <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
              <legend className="rx-role-label">Account Role</legend>
              <div className="rx-role-grid">
                <button
                  type="button"
                  id="role-officer"
                  className="rx-role-card"
                  aria-pressed={role === "field_officer"}
                  onClick={() => setRole("field_officer")}
                >
                  <span className="rx-role-icon">
                    <IconOfficer />
                  </span>
                  <span className="rx-role-text-name">Admin</span>
                </button>
                <button
                  type="button"
                  id="role-driver"
                  className="rx-role-card"
                  aria-pressed={role === "driver"}
                  onClick={() => setRole("driver")}
                >
                  <span className="rx-role-icon">
                    <IconTruck />
                  </span>
                  <span className="rx-role-text-name">Driver</span>
                </button>
              </div>
            </fieldset>
          ) : (
            <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
              <legend className="rx-role-label">Account Role</legend>
              <div className="rx-role-grid">
                <button
                  type="button"
                  id="role-driver"
                  className="rx-role-card"
                  aria-pressed={true}
                  onClick={() => setRole("driver")}
                >
                  <span className="rx-role-icon">
                    <IconTruck />
                  </span>
                  <span className="rx-role-text-name">Driver (Self-Registration)</span>
                </button>
                <button
                  type="button"
                  id="role-officer"
                  className="rx-role-card"
                  aria-pressed={false}
                  disabled
                  title="Admin accounts require administrator provisioning."
                  style={{ opacity: 0.45, cursor: "not-allowed" }}
                >
                  <span className="rx-role-icon">
                    <IconOfficer />
                  </span>
                  <span className="rx-role-text-name">Admin (Restricted)</span>
                </button>
              </div>
            </fieldset>
          )}

          {tab === "login" ? (
            <LoginFormInner role={role} onSwitchTab={() => {
              setTab("signup");
              setRole("driver");
            }} />
          ) : (
            <SignupFormInner onSwitchTab={() => setTab("login")} />
          )}

          <Link href="/home" className="rx-return-home" id="return-home-link">
            <IconHome /> Return to Home Screen
          </Link>
        </section>
        <SidePanel />
      </main>

      <HomeFooter />
    </div>
  );
}
