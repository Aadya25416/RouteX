"use client";

import React, { useState, useId } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import "./Login.css";

// MapLibre requires a browser DOM — disable SSR
const LoginMapBackground = dynamic(
  () => import("@/components/login/LoginMapBackground"),
  { ssr: false, loading: () => <div style={{ position: "fixed", inset: 0, background: "#EAF2E7", zIndex: 0 }} aria-hidden="true" /> }
);

type Tab  = "login" | "signup";
type Role = "field_officer" | "driver";

interface LoginState {
  email: string; password: string; showPassword: boolean;
  remember: boolean; isLoading: boolean; error: string | null;
}
interface SignupState {
  fullName: string; email: string; password: string; confirm: string;
  showPassword: boolean; showConfirm: boolean;
  isLoading: boolean; error: string | null;
}
interface FieldErrors {
  fullName?: string; email?: string; password?: string; confirm?: string;
}

const CURRENT_YEAR = 2026;



function IconMail() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>;
}
function IconLock() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
}
function IconUser() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>;
}
function IconEye({ off }: { off?: boolean }) {
  return off
    ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
    : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>;
}
function IconHome() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>;
}
function IconOfficer() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><circle cx="12" cy="10" r="3"/></svg>;
}
function IconTruck() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="1" y="3" width="15" height="13" rx="1"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>;
}

function SidePanel() {
  return (
    <aside className="rx-side-panel" aria-label="Illustrative route info">
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
      <div className="rx-side-demo-tag">Illustrative · Demo</div>
    </aside>
  );
}

function LoginFooter() {
  return (
    <footer className="rx-login-footer" aria-label="Site Footer">
      <div className="rx-footer-inner">
        <div className="rx-footer-grid">
          <div>
            <Link href="/home" className="rx-footer-brand-name" aria-label="RouteX home">
              <span className="rx-fbrand-route">Route</span><span className="rx-fbrand-x">X</span>
            </Link>
            <p className="rx-footer-brand-desc">Road accessibility and logistics support for the Guwahati–Tawang corridor.</p>
            <div className="rx-footer-social">
              {([["LinkedIn","M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"],["Twitter","M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"],["GitHub","M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"],["YouTube","M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"]] as [string,string][]).map(([name, d]) => (
                <a key={name} href="#" className="rx-footer-social-link" aria-label={name} onClick={e=>e.preventDefault()}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d={d} fillRule="evenodd" clipRule="evenodd"/></svg>
                </a>
              ))}
            </div>
          </div>
          <div>
            <h3 className="rx-footer-col-title">Product</h3>
            <ul className="rx-footer-links">
              <li><Link href="/map" className="rx-footer-link">Road Map (Phase 1)</Link></li>
              <li><span className="rx-footer-link-muted">Route Planning <span className="rx-footer-badge">Planned</span></span></li>
              <li><span className="rx-footer-link-muted">Incident Reporting <span className="rx-footer-badge">Planned</span></span></li>
              <li><Link href="/home#about" className="rx-footer-link">About RouteX</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="rx-footer-col-title">Resources</h3>
            <ul className="rx-footer-links">
              <li><span className="rx-footer-link-muted">Documentation <span className="rx-footer-badge">Pending</span></span></li>
              <li><Link href="/map" className="rx-footer-link">Data Sources</Link></li>
              <li><span className="rx-footer-link-muted">Coverage &amp; Limitations</span></li>
              <li><span className="rx-footer-link-muted">Accessibility</span></li>
            </ul>
          </div>
          <div>
            <h3 className="rx-footer-col-title">Company</h3>
            <ul className="rx-footer-links">
              <li><Link href="/home#about" className="rx-footer-link">Our Mission</Link></li>
              <li><span className="rx-footer-link-muted">Privacy Policy <span className="rx-footer-badge">Pending</span></span></li>
              <li><span className="rx-footer-link-muted">Terms of Use <span className="rx-footer-badge">Pending</span></span></li>
              <li><a href="mailto:support@routex.in" className="rx-footer-link">Contact Us</a></li>
            </ul>
          </div>
          <div>
            <h3 className="rx-footer-col-title">Contact</h3>
            <ul className="rx-footer-contact-list">
              <li className="rx-footer-contact-item">
                <span className="rx-footer-contact-icon"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg></span>
                <a href="mailto:support@routex.in" className="rx-footer-link">support@routex.in</a>
              </li>
              <li className="rx-footer-contact-item">
                <span className="rx-footer-contact-icon"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg></span>
                <span>Guwahati, India</span>
              </li>
              <li className="rx-footer-contact-item">
                <span className="rx-footer-contact-icon"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>
                <span>IST (UTC +5:30)</span>
              </li>
            </ul>
          </div>
        </div>
        <div className="rx-footer-bottom">
          <span>© {CURRENT_YEAR} RouteX / NER-LINK · Road network data © OpenStreetMap contributors</span>
          <span>Built for accessibility &amp; logistical resilience in Northeast India.</span>
        </div>
      </div>
    </footer>
  );
}

function LoginFormInner({ role, onSwitchTab }: { role: Role; onSwitchTab: () => void }) {
  const router = useRouter();
  const emailId = useId();
  const pwId = useId();
  const [state, setState] = useState<LoginState>({ email:"", password:"", showPassword:false, remember:false, isLoading:false, error:null });
  const [errs, setErrs] = useState<FieldErrors>({});
  const [forgotMsg, setForgotMsg] = useState<string|null>(null);

  const validate = () => {
    const e: FieldErrors = {};
    if (!state.email.trim()) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.email)) e.email = "Enter a valid email.";
    if (!state.password) e.password = "Password is required.";
    else if (state.password.length < 6) e.password = "At least 6 characters required.";
    setErrs(e);
    return Object.keys(e).length === 0;
  };
  const upd = (f:"email"|"password") => (ev:React.ChangeEvent<HTMLInputElement>) => {
    setState(s=>({...s,[f]:ev.target.value,error:null}));
    if(errs[f]) setErrs(e=>({...e,[f]:undefined}));
  };
  const handleSubmit = async (ev:React.FormEvent) => {
    ev.preventDefault(); setForgotMsg(null);
    if(!validate()) return;
    setState(s=>({...s,isLoading:true,error:null}));
    await new Promise(r=>setTimeout(r,600));
    if (role === "driver") {
      if (typeof window !== "undefined") {
        localStorage.setItem("rx_auth_role", "driver");
        localStorage.setItem("rx_driver_email", state.email);
      }
      router.push("/driver");
      return;
    }
    if (role === "field_officer") {
      if (typeof window !== "undefined") {
        localStorage.setItem("rx_auth_role", "admin");
        localStorage.setItem("rx_admin_email", state.email);
      }
      router.push("/admin");
      return;
    }
    setState(s=>({...s,isLoading:false,error:"Authentication endpoint not yet available. The RouteX backend does not expose a /api/v1/auth/login route in Phase 1."}));
  };

  return (
    <form id="login-form" onSubmit={handleSubmit} noValidate aria-label="Login form">
      <div className="rx-field">
        <label htmlFor={emailId} className="rx-field-label">Email address</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconMail /></span>
          <input id={emailId} type="email" autoComplete="email" placeholder="Enter your email" value={state.email} onChange={upd("email")} disabled={state.isLoading} aria-invalid={!!errs.email} className={`rx-input${errs.email?" rx-input--error":""}`} />
        </div>
        {errs.email && <span className="rx-field-err" role="alert">{errs.email}</span>}
      </div>
      <div className="rx-field">
        <label htmlFor={pwId} className="rx-field-label">Password</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconLock /></span>
          <input id={pwId} type={state.showPassword?"text":"password"} autoComplete="current-password" placeholder="Enter your password" value={state.password} onChange={upd("password")} disabled={state.isLoading} aria-invalid={!!errs.password} className={`rx-input rx-input--pw${errs.password?" rx-input--error":""}`} />
          <button type="button" className="rx-pw-toggle" onClick={()=>setState(s=>({...s,showPassword:!s.showPassword}))} aria-label={state.showPassword?"Hide password":"Show password"}><IconEye off={state.showPassword}/></button>
        </div>
        {errs.password && <span className="rx-field-err" role="alert">{errs.password}</span>}
      </div>
      <div className="rx-remember-row">
        <label className="rx-remember-label">
          <input type="checkbox" className="rx-checkbox" checked={state.remember} onChange={e=>setState(s=>({...s,remember:e.target.checked}))} />
          Remember me
        </label>
        <button type="button" className="rx-forgot-link" onClick={()=>setForgotMsg("Password recovery is not yet available in Phase 1. Please contact the administrator.")}>Forgot password?</button>
      </div>
      {forgotMsg && <div className="rx-info-banner" role="status"><span>ℹ</span><span>{forgotMsg}</span></div>}
      {state.error && <div className="rx-err-banner" role="alert"><span>⚠</span><span>{state.error}</span></div>}
      <button id="login-submit-btn" type="submit" className="rx-primary-btn" disabled={state.isLoading} aria-busy={state.isLoading}>
        {state.isLoading?<><span className="rx-spinner"/><span>Signing in…</span></>:<span>Sign In →</span>}
      </button>
      {role === "driver" && (
        <div style={{ marginTop: "10px", textAlign: "center" }}>
          <Link href="/driver" className="rx-forgot-link" style={{ color: "#16A779", fontWeight: 600 }}>
            Quick Demo: Access Driver Dashboard Directly →
          </Link>
        </div>
      )}
      {role === "field_officer" && (
        <div style={{ marginTop: "10px", textAlign: "center" }}>
          <Link href="/admin" className="rx-forgot-link" style={{ color: "#16A779", fontWeight: 600 }}>
            Quick Demo: Access System Admin Dashboard Directly →
          </Link>
        </div>
      )}
      <div className="rx-or-divider">OR</div>
      <button type="button" className="rx-secondary-btn" onClick={onSwitchTab}>Create a new account</button>
      <input type="hidden" name="role" value={role} />
    </form>
  );
}

function SignupFormInner({ role, onSwitchTab }: { role: Role; onSwitchTab: () => void }) {
  const router = useRouter();
  const nameId = useId(); const emailId = useId(); const pwId = useId(); const confirmId = useId();
  const [state, setState] = useState<SignupState>({ fullName:"", email:"", password:"", confirm:"", showPassword:false, showConfirm:false, isLoading:false, error:null });
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
    setErrs(e); return Object.keys(e).length === 0;
  };
  const upd = (f:keyof Pick<SignupState,"fullName"|"email"|"password"|"confirm">) => (ev:React.ChangeEvent<HTMLInputElement>) => {
    setState(s=>({...s,[f]:ev.target.value,error:null}));
    if(errs[f]) setErrs(e=>({...e,[f]:undefined}));
  };
  const handleSubmit = async (ev:React.FormEvent) => {
    ev.preventDefault();
    if(!validate()) return;
    setState(s=>({...s,isLoading:true,error:null}));
    await new Promise(r=>setTimeout(r,600));
    if (role === "driver") {
      if (typeof window !== "undefined") {
        localStorage.setItem("rx_auth_role", "driver");
        localStorage.setItem("rx_driver_name", state.fullName);
        localStorage.setItem("rx_driver_email", state.email);
      }
      router.push("/driver");
      return;
    }
    if (role === "field_officer") {
      if (typeof window !== "undefined") {
        localStorage.setItem("rx_auth_role", "admin");
        localStorage.setItem("rx_admin_name", state.fullName);
        localStorage.setItem("rx_admin_email", state.email);
      }
      router.push("/admin");
      return;
    }
    setState(s=>({...s,isLoading:false,error:"Registration endpoint not yet available. The RouteX backend does not expose a /api/v1/auth/register route in Phase 1."}));
  };

  return (
    <form id="signup-form" onSubmit={handleSubmit} noValidate aria-label="Sign up form">
      {role==="field_officer" && <div className="rx-info-banner" role="note"><span>ℹ</span><span>Field Officer / Admin registration requires backend approval. Contact your administrator.</span></div>}
      <div className="rx-field">
        <label htmlFor={nameId} className="rx-field-label">Full name</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconUser /></span>
          <input id={nameId} type="text" autoComplete="name" placeholder="Your full name" value={state.fullName} onChange={upd("fullName")} disabled={state.isLoading} aria-invalid={!!errs.fullName} className={`rx-input${errs.fullName?" rx-input--error":""}`} />
        </div>
        {errs.fullName && <span className="rx-field-err" role="alert">{errs.fullName}</span>}
      </div>
      <div className="rx-field">
        <label htmlFor={emailId} className="rx-field-label">Email address</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconMail /></span>
          <input id={emailId} type="email" autoComplete="email" placeholder="you@example.com" value={state.email} onChange={upd("email")} disabled={state.isLoading} aria-invalid={!!errs.email} className={`rx-input${errs.email?" rx-input--error":""}`} />
        </div>
        {errs.email && <span className="rx-field-err" role="alert">{errs.email}</span>}
      </div>
      <div className="rx-field">
        <label htmlFor={pwId} className="rx-field-label">Password</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconLock /></span>
          <input id={pwId} type={state.showPassword?"text":"password"} autoComplete="new-password" placeholder="Create a password" value={state.password} onChange={upd("password")} disabled={state.isLoading} aria-invalid={!!errs.password} className={`rx-input rx-input--pw${errs.password?" rx-input--error":""}`} />
          <button type="button" className="rx-pw-toggle" onClick={()=>setState(s=>({...s,showPassword:!s.showPassword}))} aria-label={state.showPassword?"Hide":"Show"}><IconEye off={state.showPassword}/></button>
        </div>
        {errs.password && <span className="rx-field-err" role="alert">{errs.password}</span>}
      </div>
      <div className="rx-field">
        <label htmlFor={confirmId} className="rx-field-label">Confirm password</label>
        <div className="rx-input-wrap">
          <span className="rx-input-icon"><IconLock /></span>
          <input id={confirmId} type={state.showConfirm?"text":"password"} autoComplete="new-password" placeholder="Repeat your password" value={state.confirm} onChange={upd("confirm")} disabled={state.isLoading} aria-invalid={!!errs.confirm} className={`rx-input rx-input--pw${errs.confirm?" rx-input--error":""}`} />
          <button type="button" className="rx-pw-toggle" onClick={()=>setState(s=>({...s,showConfirm:!s.showConfirm}))} aria-label={state.showConfirm?"Hide":"Show"}><IconEye off={state.showConfirm}/></button>
        </div>
        {errs.confirm && <span className="rx-field-err" role="alert">{errs.confirm}</span>}
      </div>
      {state.error && <div className="rx-err-banner" role="alert"><span>⚠</span><span>{state.error}</span></div>}
      <p className="rx-terms-text">By creating an account you acknowledge this is a <strong>Phase 1 prototype</strong>. No personal data is transmitted to a live server.</p>
      <button id="signup-submit-btn" type="submit" className="rx-primary-btn" disabled={state.isLoading} aria-busy={state.isLoading}>
        {state.isLoading?<><span className="rx-spinner"/><span>Creating account…</span></>:<span>Create Account →</span>}
      </button>
      {role === "driver" && (
        <div style={{ marginTop: "10px", textAlign: "center" }}>
          <Link href="/driver" className="rx-forgot-link" style={{ color: "#16A779", fontWeight: 600 }}>
            Quick Demo: Access Driver Dashboard Directly →
          </Link>
        </div>
      )}
      {role === "field_officer" && (
        <div style={{ marginTop: "10px", textAlign: "center" }}>
          <Link href="/admin" className="rx-forgot-link" style={{ color: "#16A779", fontWeight: 600 }}>
            Quick Demo: Access System Admin Dashboard Directly →
          </Link>
        </div>
      )}
      <input type="hidden" name="role" value={role} />
      <div className="rx-signin-link-row">Already have an account? <button type="button" onClick={onSwitchTab}>Sign in</button></div>
    </form>
  );
}

export default function LoginPage() {
  const [tab, setTab]   = useState<Tab>("login");
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
        <span className="rx-login-header-badge" aria-label="Prototype phase">● Prototype</span>
      </header>

      <main className="rx-login-body" id="login-main">
        <section className="rx-auth-card" aria-label="Authentication">
          <div className="rx-tab-row" role="tablist" aria-label="Authentication mode">
            <button id="tab-login" role="tab" className="rx-tab-btn" aria-selected={tab==="login"} onClick={()=>setTab("login")}>Login</button>
            <button id="tab-signup" role="tab" className="rx-tab-btn" aria-selected={tab==="signup"} onClick={()=>setTab("signup")}>Sign Up</button>
          </div>
          <h1 className="rx-card-title">{tab==="login"?"Welcome back":"Create your account"}</h1>
          <p className="rx-card-sub">{tab==="login"?"Sign in to access your route intelligence dashboard.":"Join RouteX to monitor and plan routes across Northeast India."}</p>
          <fieldset style={{border:"none",padding:0,margin:0}}>
            <legend className="rx-role-label">I am a</legend>
            <div className="rx-role-grid">
              <button type="button" id="role-officer" className="rx-role-card" aria-pressed={role==="field_officer"} onClick={()=>setRole("field_officer")}>
                <span className="rx-role-icon"><IconOfficer /></span>
                <span><div className="rx-role-text-name">Field Officer / Admin</div><div className="rx-role-text-desc">Manage, Monitor, Plan</div></span>
              </button>
              <button type="button" id="role-driver" className="rx-role-card" aria-pressed={role==="driver"} onClick={()=>setRole("driver")}>
                <span className="rx-role-icon"><IconTruck /></span>
                <span><div className="rx-role-text-name">Driver</div><div className="rx-role-text-desc">View Routes, Report</div></span>
              </button>
            </div>
          </fieldset>
          {tab==="login"
            ? <LoginFormInner role={role} onSwitchTab={()=>setTab("signup")} />
            : <SignupFormInner role={role} onSwitchTab={()=>setTab("login")} />
          }
          <Link href="/home" className="rx-return-home" id="return-home-link">
            <IconHome /> Return to Home Screen
          </Link>
        </section>
        <SidePanel />
      </main>

      <LoginFooter />
    </div>
  );
}
