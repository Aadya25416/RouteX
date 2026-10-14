"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

interface HomeNavbarProps {
  activeSection?: string;
}

export default function HomeNavbar({ activeSection = "overview" }: HomeNavbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [currentSection, setCurrentSection] = useState(activeSection);

  useEffect(() => {
    function handleScroll() {
      const sections = ["overview", "features", "how-it-works", "about"];
      const scrollY = window.scrollY;

      for (const sectionId of sections) {
        const el = document.getElementById(sectionId);
        if (el) {
          const top = el.offsetTop - 120;
          const height = el.offsetHeight;
          if (scrollY >= top && scrollY < top + height) {
            setCurrentSection(sectionId);
            break;
          }
        }
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { label: "Overview", href: "#overview", id: "overview" },
    { label: "Features", href: "#features", id: "features" },
    { label: "How It Works", href: "#how-it-works", id: "how-it-works" },
    { label: "About", href: "#about", id: "about" },
  ];

  return (
    <header className="home-nav-header">
      <div className="home-nav-container">
        {/* Left: Brand Wordmark */}
        <Link href="/home" className="home-nav-brand" aria-label="RouteX Home">
          <span className="home-brand-route">Route</span>
          <span className="home-brand-x">X</span>
        </Link>

        {/* Center: Desktop Navigation Links */}
        <nav className="home-nav-menu" aria-label="Main Navigation">
          {navLinks.map((link) => {
            const isActive = currentSection === link.id;
            return (
              <a
                key={link.id}
                href={link.href}
                className={`home-nav-link ${isActive ? "home-nav-link-active" : ""}`}
              >
                {link.label}
                {isActive && <span className="home-nav-indicator" aria-hidden="true" />}
              </a>
            );
          })}
        </nav>

        {/* Right: Actions */}
        <div className="home-nav-actions">
          <Link href="/login" className="home-signin-link" id="home-signin-link">
            Sign In
          </Link>
          <Link href="/login" className="home-getstarted-btn" id="home-getstarted-nav-btn">
            <span>Get Started</span>
            <span className="home-getstarted-arrow" aria-hidden="true">→</span>
          </Link>

          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            className="home-mobile-toggle"
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <span className={`home-hamburger-bar ${mobileMenuOpen ? "open" : ""}`} />
            <span className={`home-hamburger-bar ${mobileMenuOpen ? "open" : ""}`} />
            <span className={`home-hamburger-bar ${mobileMenuOpen ? "open" : ""}`} />
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="home-mobile-drawer" role="dialog" aria-modal="true">
          <nav className="home-mobile-nav">
            {navLinks.map((link) => (
              <a
                key={link.id}
                href={link.href}
                className="home-mobile-link"
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <div className="home-mobile-actions">
              <Link
                href="/login"
                className="home-mobile-signin"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sign In
              </Link>
              <Link
                href="/login"
                className="home-mobile-getstarted"
                onClick={() => setMobileMenuOpen(false)}
              >
                Get Started →
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
