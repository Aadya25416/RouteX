import React from "react";
import type { Metadata } from "next";
import "@/components/home/HomePage.css";
import HomeNavbar from "@/components/home/HomeNavbar";
import HomeHero from "@/components/home/HomeHero";
import HowItWorks from "@/components/home/HowItWorks";
import FeaturesSection from "@/components/home/FeaturesSection";
import AboutSection from "@/components/home/AboutSection";
import HomeFooter from "@/components/home/HomeFooter";

export const metadata: Metadata = {
  title: "RouteX — Stronger Connections | AI Route Intelligence",
  description:
    "RouteX homepage: Safer routes and stronger connections for high-altitude logistics corridors and Northeast India. AI-powered route intelligence for logistics.",
};

export default function HomePage() {
  return (
    <div className="routex-home-root">
      {/* 1. Sticky Navigation Bar */}
      <HomeNavbar />

      {/* 2. Hero Section with Regional Road Map Visual */}
      <HomeHero />

      {/* 3. How It Works Section */}
      <HowItWorks />

      {/* 4. Features Section */}
      <FeaturesSection />

      {/* 5. About Section */}
      <AboutSection />

      {/* 6. Multi-Column Footer */}
      <HomeFooter />
    </div>
  );
}
