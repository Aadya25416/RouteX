"use client";

import React, { useEffect, useRef, useState } from "react";

interface LetterTransform {
  rotateX: number;
  rotateY: number;
  translateZ: number;
  translateX: number;
  translateY: number;
}

const LETTERS = ["R", "o", "u", "t", "e", "X"] as const;

const mkRest = (): LetterTransform => ({
  rotateX: 0,
  rotateY: 0,
  translateZ: 0,
  translateX: 0,
  translateY: 0,
});

function getReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function applyTransforms(
  els: (HTMLSpanElement | null)[],
  transforms: LetterTransform[]
) {
  transforms.forEach((t, i) => {
    const el = els[i];
    if (!el) return;
    el.style.transform = [
      "perspective(700px)",
      `translateX(${t.translateX.toFixed(2)}px)`,
      `translateY(${t.translateY.toFixed(2)}px)`,
      `translateZ(${t.translateZ.toFixed(2)}px)`,
      `rotateX(${t.rotateX.toFixed(2)}deg)`,
      `rotateY(${t.rotateY.toFixed(2)}deg)`,
    ].join(" ");
  });
}

export default function RouteXTitle3D({ visible }: { visible: boolean }) {
  const letterRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const curRef = useRef<LetterTransform[]>(LETTERS.map(mkRest));
  const tgtRef = useRef<LetterTransform[]>(LETTERS.map(mkRest));
  const rafRef = useRef<number | null>(null);
  const runningRef = useRef(false);

  const [reducedMotion, setReducedMotion] = useState<boolean>(getReducedMotion);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (!visible || reducedMotion) return;

    function step() {
      const speed = 0.08;
      let stillMoving = false;

      curRef.current = curRef.current.map((c, i) => {
        const tgt = tgtRef.current[i];
        const n: LetterTransform = {
          rotateX: lerp(c.rotateX, tgt.rotateX, speed),
          rotateY: lerp(c.rotateY, tgt.rotateY, speed),
          translateZ: lerp(c.translateZ, tgt.translateZ, speed),
          translateX: lerp(c.translateX, tgt.translateX, speed),
          translateY: lerp(c.translateY, tgt.translateY, speed),
        };
        if (
          Math.abs(n.rotateX - tgt.rotateX) > 0.01 ||
          Math.abs(n.rotateY - tgt.rotateY) > 0.01 ||
          Math.abs(n.translateZ - tgt.translateZ) > 0.01
        ) {
          stillMoving = true;
        }
        return n;
      });

      applyTransforms(letterRefs.current, curRef.current);

      if (stillMoving) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        rafRef.current = null;
        runningRef.current = false;
      }
    }

    function kickLoop() {
      if (runningRef.current) return;
      runningRef.current = true;
      rafRef.current = requestAnimationFrame(step);
    }

    function onMouseMove(e: MouseEvent) {
      // Ignore mouse tilt on touch devices
      if ("ontouchstart" in window && window.matchMedia("(pointer: coarse)").matches) {
        return;
      }

      letterRefs.current.forEach((el, i) => {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = e.clientX - cx;
        const dy = e.clientY - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxDist = 260;
        const strength = Math.max(0, 1 - dist / maxDist);

        tgtRef.current[i] = {
          rotateY: (dx / maxDist) * 16 * strength,
          rotateX: -(dy / maxDist) * 16 * strength,
          translateX: (dx / maxDist) * 6 * strength,
          translateY: (dy / maxDist) * 6 * strength,
          translateZ: 18 * strength,
        };
      });
      kickLoop();
    }

    function onMouseLeave() {
      tgtRef.current = LETTERS.map(mkRest);
      kickLoop();
    }

    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("mouseleave", onMouseLeave, { passive: true });

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseleave", onMouseLeave);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
        runningRef.current = false;
      }
    };
  }, [visible, reducedMotion]);

  return (
    <div className="routex-title-wrapper">
      <div
        className={`routex-title-3d ${visible ? "routex-title-visible" : ""}`}
        role="heading"
        aria-level={1}
        aria-label="RouteX"
      >
        {LETTERS.map((char, idx) => {
          const isX = idx === 5;
          return (
            <span
              key={idx}
              ref={(el) => {
                letterRefs.current[idx] = el;
              }}
              className={`routex-char ${isX ? "routex-char-x" : "routex-char-route"}`}
              style={{ animationDelay: `${1.0 + idx * 0.06}s` }}
              aria-hidden="true"
            >
              {char}
            </span>
          );
        })}

        {/* Subtle light sweep reflection */}
        <span className="routex-light-sweep" aria-hidden="true" />
      </div>

      {/* Corridor Description Subtitle */}
      <p className="routex-corridor-desc" aria-label="Corridor summary">
        Road conditions, incidents and routes
        <br />
        for the Guwahati-Tawang corridor, in
        <br />
        one map.
      </p>
    </div>
  );
}
