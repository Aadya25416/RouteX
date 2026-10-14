import React from "react";
import Link from "next/link";
import "./HomeFooter.css";

const CURRENT_YEAR = 2026;

export default function HomeFooter() {
  return (
    <footer className="home-footer" id="contact" aria-label="Site Footer">
      <div className="home-footer-container">
        {/* Top 5-Column Grid */}
        <div className="footer-grid">
          {/* Column 1: Brand & Regional Bio */}
          <div className="footer-col footer-col-brand">
            <Link href="/home" className="footer-brand" aria-label="RouteX Home">
              <span className="brand-route">Route</span>
              <span className="brand-x">X</span>
              <span className="footer-brand-badge">Logistics</span>
            </Link>
            <p className="footer-brand-desc">
              Safer routes and resilient road network intelligence for the Guwahati–Tawang corridor and Northeast India.
            </p>
            <div className="footer-org-tag">
              <span>🌐</span>
              <span>NER-LINK Infrastructure Network</span>
            </div>
          </div>

          {/* Column 2: Product & Capabilities */}
          <div className="footer-col">
            <h4 className="footer-heading">Capabilities</h4>
            <ul className="footer-links">
              <li>
                <Link href="/map" className="footer-link">
                  Road Network Map
                </Link>
              </li>
              <li>
                <Link href="/admin/route-planning" className="footer-link">
                  Route Planning Engine
                </Link>
              </li>
              <li>
                <Link href="/driver/navigation" className="footer-link">
                  Driver Navigation
                </Link>
              </li>
              <li>
                <Link href="/admin/incidents" className="footer-link">
                  Hazard &amp; Disruption Log
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 3: Platform Portals */}
          <div className="footer-col">
            <h4 className="footer-heading">Portals</h4>
            <ul className="footer-links">
              <li>
                <Link href="/driver" className="footer-link">
                  Driver Dashboard
                </Link>
              </li>
              <li>
                <Link href="/admin" className="footer-link">
                  System Admin Console
                </Link>
              </li>
              <li>
                <Link href="/login" className="footer-link">
                  Staff Login / Register
                </Link>
              </li>
              <li>
                <Link href="/home" className="footer-link">
                  Corridor Home
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 4: Platform Sections */}
          <div className="footer-col">
            <h4 className="footer-heading">Corridor Info</h4>
            <ul className="footer-links">
              <li>
                <Link href="/home#overview" className="footer-link">
                  Corridor Overview
                </Link>
              </li>
              <li>
                <Link href="/home#how-it-works" className="footer-link">
                  How It Works
                </Link>
              </li>
              <li>
                <Link href="/home#features" className="footer-link">
                  Platform Features
                </Link>
              </li>
              <li>
                <Link href="/home#about" className="footer-link">
                  About NER-LINK
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 5: Regional Operations */}
          <div className="footer-col">
            <h4 className="footer-heading">Regional Ops</h4>
            <ul className="footer-contact-list">
              <li className="contact-item">
                <span className="contact-icon" aria-hidden="true">📍</span>
                <div>
                  <span className="contact-text-main">Guwahati, Assam</span>
                  <span className="contact-text-sub">Regional Logistics Hub</span>
                </div>
              </li>
              <li className="contact-item">
                <span className="contact-icon" aria-hidden="true">🛣️</span>
                <div>
                  <span className="contact-text-main">Guwahati–Tawang</span>
                  <span className="contact-text-sub">NH-27 / NH-13 Corridor</span>
                </div>
              </li>
              <li className="contact-item">
                <span className="contact-icon" aria-hidden="true">🕒</span>
                <div>
                  <span className="contact-text-main">IST (UTC +5:30)</span>
                  <span className="contact-text-sub">Operational Hours</span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="footer-bottom-bar">
          <div className="footer-copyright">
            © {CURRENT_YEAR} RouteX / NER-LINK · Road network data © OpenStreetMap contributors
          </div>
          <div className="footer-disclaimer">
            Built for accessibility &amp; logistical resilience in Northeast India.
          </div>
        </div>
      </div>
    </footer>
  );
}
