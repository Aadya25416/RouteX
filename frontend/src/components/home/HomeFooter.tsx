import React from "react";
import Link from "next/link";

const CURRENT_YEAR = 2026;

export default function HomeFooter() {
  return (
    <footer className="home-footer" id="contact" aria-label="Site Footer">
      <div className="home-footer-container">
        {/* Top 5-Column Grid */}
        <div className="footer-grid">
          {/* Column 1: Brand & Bio */}
          <div className="footer-col footer-col-brand">
            <Link href="/home" className="footer-brand" aria-label="RouteX Home">
              <span className="brand-route">Route</span>
              <span className="brand-x">X</span>
            </Link>
            <p className="footer-brand-desc">
              Road accessibility and logistics support for the Guwahati–Tawang corridor and Northeast India.
            </p>
            {/* Social Icons */}
            <div className="footer-social-row" aria-label="Social links">
              {/* LinkedIn */}
              <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="LinkedIn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                </svg>
              </a>
              {/* Twitter / X */}
              <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="Twitter">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
              </a>
              {/* GitHub */}
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="GitHub">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                </svg>
              </a>
              {/* YouTube */}
              <a href="https://youtube.com" target="_blank" rel="noopener noreferrer" className="social-link" aria-label="YouTube">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
              </a>
            </div>
          </div>

          {/* Column 2: Product */}
          <div className="footer-col">
            <h4 className="footer-heading">Product</h4>
            <ul className="footer-links">
              <li>
                <Link href="/map" className="footer-link">
                  Road Map (Phase 1)
                </Link>
              </li>
              <li>
                <a href="#how-it-works" className="footer-link">
                  Route Planning <span className="footer-badge-planned">Planned</span>
                </a>
              </li>
              <li>
                <a href="#features" className="footer-link">
                  Incident Reporting <span className="footer-badge-planned">Planned</span>
                </a>
              </li>
              <li>
                <a href="#about" className="footer-link">
                  Feature Roadmap
                </a>
              </li>
            </ul>
          </div>

          {/* Column 3: Resources */}
          <div className="footer-col">
            <h4 className="footer-heading">Resources</h4>
            <ul className="footer-links">
              <li>
                <a href="#about" className="footer-link">Documentation</a>
              </li>
              <li>
                <Link href="/map" className="footer-link">Data Sources</Link>
              </li>
              <li>
                <a href="#overview" className="footer-link">Coverage & Limitations</a>
              </li>
              <li>
                <a href="#overview" className="footer-link">Accessibility</a>
              </li>
            </ul>
          </div>

          {/* Column 4: Company */}
          <div className="footer-col">
            <h4 className="footer-heading">Company</h4>
            <ul className="footer-links">
              <li>
                <a href="#about" className="footer-link">About RouteX</a>
              </li>
              <li>
                <span className="footer-link-muted">Privacy Policy (Pending)</span>
              </li>
              <li>
                <span className="footer-link-muted">Terms of Use (Pending)</span>
              </li>
              <li>
                <a href="#contact" className="footer-link">Contact Us</a>
              </li>
            </ul>
          </div>

          {/* Column 5: Contact */}
          <div className="footer-col">
            <h4 className="footer-heading">Contact</h4>
            <ul className="footer-contact-list">
              <li className="contact-item">
                <span className="contact-icon">✉</span>
                <a href="mailto:support@routex.in" className="contact-link">
                  support@routex.in
                </a>
              </li>
              <li className="contact-item">
                <span className="contact-icon">📍</span>
                <span>Guwahati, India</span>
              </li>
              <li className="contact-item">
                <span className="contact-icon">🕒</span>
                <span>IST (UTC +5:30)</span>
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
            Built for accessibility & logistical resilience in Northeast India.
          </div>
        </div>
      </div>
    </footer>
  );
}
