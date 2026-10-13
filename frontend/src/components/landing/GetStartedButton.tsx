"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

interface GetStartedButtonProps {
  revealDelayMs?: number;
}

function getInitialVisible(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function GetStartedButton({ revealDelayMs = 3500 }: GetStartedButtonProps) {
  const [visible, setVisible] = useState<boolean>(getInitialVisible);

  useEffect(() => {
    if (visible) return;

    const timer = setTimeout(() => {
      setVisible(true);
    }, revealDelayMs);

    return () => clearTimeout(timer);
  }, [revealDelayMs, visible]);

  return (
    <div
      className={`routex-btn-container ${visible ? "routex-btn-visible" : "routex-btn-hidden"}`}
      aria-hidden={!visible}
    >
      <Link
        href="/home"
        id="get-started-btn"
        className="routex-pill-btn"
        tabIndex={visible ? 0 : -1}
        aria-label="Get started — proceed to login"
      >
        <span className="routex-btn-text">Get started</span>
        <span className="routex-btn-arrow" aria-hidden="true">&gt;</span>
      </Link>
    </div>
  );
}
