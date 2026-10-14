"use client";

import React, { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

export default function ScrollToExplore() {
  const router = useRouter();
  const navigatedRef = useRef(false);

  useEffect(() => {
    function handleWheel(e: WheelEvent) {
      if (navigatedRef.current) return;
      if (e.deltaY > 20) {
        navigatedRef.current = true;
        router.push("/home");
      }
    }

    window.addEventListener("wheel", handleWheel, { passive: true });
    return () => {
      window.removeEventListener("wheel", handleWheel);
    };
  }, [router]);

  function handleClick() {
    if (navigatedRef.current) return;
    navigatedRef.current = true;
    router.push("/home");
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  }

  return (
    <button
      type="button"
      className="routex-scroll-explore"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      aria-label="Scroll to explore — navigate to login"
      id="scroll-to-explore-btn"
    >
      <span className="routex-scroll-text">Scroll to explore</span>
      <div className="routex-mouse-icon" aria-hidden="true">
        <span className="routex-mouse-wheel" />
      </div>
    </button>
  );
}
