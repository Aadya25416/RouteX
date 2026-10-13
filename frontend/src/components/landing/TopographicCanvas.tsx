"use client";

import React, { useEffect, useRef } from "react";

interface TopographicCanvasProps {
  onCoordinateChange?: (lat: string, lon: string) => void;
}

interface Point {
  x: number;
  y: number;
}

export default function TopographicCanvas({ onCoordinateChange }: TopographicCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const mouseRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = 1;

    function resize() {
      if (!canvas) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }

    resize();
    window.addEventListener("resize", resize);

    function handleMouseMove(e: MouseEvent) {
      mouseRef.current = { x: e.clientX, y: e.clientY };
      if (onCoordinateChange && width > 0 && height > 0) {
        // Map cursor position to illustrative coordinates around Assam/Arunachal Pradesh corridor
        // Guwahati is approx 26.14°N, 91.73°E; Tawang is approx 27.58°N, 91.86°E
        const latVal = 25.0 + ((height - e.clientY) / height) * 3.0;
        const lonVal = 91.0 + (e.clientX / width) * 2.0;
        onCoordinateChange(latVal.toFixed(4), lonVal.toFixed(4));
      }
    }

    function handleMouseLeave() {
      mouseRef.current = null;
    }

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    document.addEventListener("mouseleave", handleMouseLeave);

    // Deterministic spline points for Guwahati -> Tawang route (normalized 0..1)
    const routeNormPoints: Point[] = [
      { x: 0.10, y: 0.74 }, // GUWAHATI
      { x: 0.18, y: 0.71 },
      { x: 0.27, y: 0.62 }, // SONAPUR (crest)
      { x: 0.36, y: 0.65 },
      { x: 0.44, y: 0.70 }, // NAGAON (trough)
      { x: 0.53, y: 0.61 },
      { x: 0.61, y: 0.50 },
      { x: 0.69, y: 0.40 }, // HAZARD FORK
      { x: 0.76, y: 0.34 }, // DIRANG
      { x: 0.83, y: 0.27 },
      { x: 0.91, y: 0.19 }, // TAWANG
    ];

    // Branch hazard path (dashed line)
    const hazardBranchNorm: Point[] = [
      { x: 0.69, y: 0.40 },
      { x: 0.72, y: 0.47 },
      { x: 0.74, y: 0.55 },
      { x: 0.77, y: 0.62 },
    ];

    function drawTopographicLines(c: CanvasRenderingContext2D, t: number) {
      c.save();
      c.lineWidth = 1;
      const count = 14;
      const spacing = height / (count + 1);

      for (let i = 1; i <= count; i++) {
        const baseY = i * spacing;
        c.beginPath();
        c.strokeStyle = "rgba(22, 167, 121, 0.08)";

        const segments = 40;
        for (let s = 0; s <= segments; s++) {
          const x = (s / segments) * width;
          // Smooth sine harmonics to evoke mountain topography
          const wave =
            Math.sin(s * 0.25 + i * 0.7) * 24 +
            Math.cos(s * 0.4 + i * 1.1) * 16 +
            Math.sin(s * 0.1 + (reducedMotion ? 0 : t * 0.0003)) * 8;
          const y = baseY + wave;
          if (s === 0) c.moveTo(x, y);
          else c.lineTo(x, y);
        }
        c.stroke();
      }
      c.restore();
    }

    function drawGrid(c: CanvasRenderingContext2D) {
      c.save();
      c.strokeStyle = "rgba(22, 167, 121, 0.04)";
      c.lineWidth = 1;

      const gridSize = 90;
      for (let x = 0; x <= width; x += gridSize) {
        c.beginPath();
        c.moveTo(x, 0);
        c.lineTo(x, height);
        c.stroke();
      }
      for (let y = 0; y <= height; y += gridSize) {
        c.beginPath();
        c.moveTo(0, y);
        c.lineTo(width, y);
        c.stroke();
      }
      c.restore();
    }

    function render(timestamp: number) {
      if (!ctx) return;
      if (!startTimeRef.current) startTimeRef.current = timestamp;
      const elapsed = timestamp - startTimeRef.current;
      const drawProgress = reducedMotion ? 1 : Math.min(elapsed / 2000, 1);

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      // 1. Background fill
      ctx.fillStyle = "#06201A";
      ctx.fillRect(0, 0, width, height);

      // 2. Faint grid
      drawGrid(ctx);

      // 3. Topographic lines
      drawTopographicLines(ctx, elapsed);

      // 4. Main Highway Route Path (Guwahati -> Tawang)
      const absPoints = routeNormPoints.map((p) => ({
        x: p.x * width,
        y: p.y * height,
      }));

      // Calculate path up to drawProgress
      const totalPoints = absPoints.length;
      const visibleCount = Math.max(1, Math.floor(drawProgress * totalPoints));

      if (absPoints.length > 1) {
        // Outer green glow
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(absPoints[0].x, absPoints[0].y);
        for (let i = 1; i < visibleCount; i++) {
          const xc = (absPoints[i - 1].x + absPoints[i].x) / 2;
          const yc = (absPoints[i - 1].y + absPoints[i].y) / 2;
          ctx.quadraticCurveTo(absPoints[i - 1].x, absPoints[i - 1].y, xc, yc);
        }
        if (visibleCount < totalPoints) {
          ctx.lineTo(absPoints[visibleCount - 1].x, absPoints[visibleCount - 1].y);
        }
        ctx.strokeStyle = "rgba(22, 167, 121, 0.35)";
        ctx.lineWidth = 6;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.stroke();

        // Inner sharp route line
        ctx.beginPath();
        ctx.moveTo(absPoints[0].x, absPoints[0].y);
        for (let i = 1; i < visibleCount; i++) {
          const xc = (absPoints[i - 1].x + absPoints[i].x) / 2;
          const yc = (absPoints[i - 1].y + absPoints[i].y) / 2;
          ctx.quadraticCurveTo(absPoints[i - 1].x, absPoints[i - 1].y, xc, yc);
        }
        if (visibleCount < totalPoints) {
          ctx.lineTo(absPoints[visibleCount - 1].x, absPoints[visibleCount - 1].y);
        }
        ctx.strokeStyle = "#8FCFC0";
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.restore();
      }

      // 5. Hazard branch (dotted/dashed line from fork)
      if (drawProgress > 0.6) {
        const hPoints = hazardBranchNorm.map((p) => ({
          x: p.x * width,
          y: p.y * height,
        }));
        ctx.save();
        ctx.beginPath();
        ctx.setLineDash([4, 6]);
        ctx.moveTo(hPoints[0].x, hPoints[0].y);
        for (let i = 1; i < hPoints.length; i++) {
          ctx.lineTo(hPoints[i].x, hPoints[i].y);
        }
        ctx.strokeStyle = "rgba(143, 207, 192, 0.4)";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.restore();
      }

      // 6. Hazard box and callout at fork (x: 0.69, y: 0.40)
      if (drawProgress > 0.65) {
        const hazardX = 0.69 * width;
        const hazardY = 0.40 * height;

        ctx.save();
        // Pulsing amber halo
        const pulse = reducedMotion ? 1 : (Math.sin(elapsed * 0.005) + 1) / 2;
        ctx.beginPath();
        ctx.arc(hazardX, hazardY, 6 + pulse * 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(244, 182, 74, ${0.4 + pulse * 0.4})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Amber hazard center dot
        ctx.beginPath();
        ctx.arc(hazardX, hazardY, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = "#F4B64A";
        ctx.fill();

        // Connecting amber line to box
        const boxX = hazardX + 28;
        const boxY = hazardY + 6;
        const boxW = 145;
        const boxH = 40;

        ctx.beginPath();
        ctx.moveTo(hazardX, hazardY);
        ctx.lineTo(boxX, boxY + boxH / 2);
        ctx.strokeStyle = "rgba(244, 182, 74, 0.7)";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Box background & border
        ctx.fillStyle = "rgba(6, 32, 26, 0.85)";
        ctx.fillRect(boxX, boxY, boxW, boxH);
        ctx.strokeStyle = "#F4B64A";
        ctx.lineWidth = 1;
        ctx.strokeRect(boxX, boxY, boxW, boxH);

        // Box text
        ctx.fillStyle = "#F4B64A";
        ctx.font = 'bold 10px var(--font-geist-mono, "JetBrains Mono", monospace)';
        ctx.fillText("LANDSLIDE REPORT", boxX + 8, boxY + 16);

        ctx.fillStyle = "rgba(244, 182, 74, 0.8)";
        ctx.font = '9px var(--font-geist-mono, "JetBrains Mono", monospace)';
        ctx.fillText("unverified · illustrative", boxX + 8, boxY + 30);
        ctx.restore();
      }

      // 7. Corridor Nodes (Guwahati, Sonapur, Nagaon, Dirang, Tawang)
      const nodes = [
        { label: "GUWAHATI", x: 0.10 * width, y: 0.74 * height, pos: "top" },
        { label: "SONAPUR",  x: 0.27 * width, y: 0.62 * height, pos: "top" },
        { label: "NAGAON",   x: 0.44 * width, y: 0.70 * height, pos: "bottom" },
        { label: "DIRANG",   x: 0.76 * width, y: 0.34 * height, pos: "top" },
        { label: "TAWANG",   x: 0.91 * width, y: 0.19 * height, pos: "top" },
      ];

      nodes.forEach((n, idx) => {
        if (drawProgress < (idx + 1) / nodes.length * 0.9 && !reducedMotion) return;

        ctx.save();
        // Hollow ring
        ctx.beginPath();
        ctx.arc(n.x, n.y, 4.5, 0, Math.PI * 2);
        ctx.strokeStyle = "#8FCFC0";
        ctx.lineWidth = 2;
        ctx.fillStyle = "#06201A";
        ctx.fill();
        ctx.stroke();

        // Inner glowing dot for Tawang
        if (n.label === "TAWANG") {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = "#16A779";
          ctx.fill();
        }

        // Label
        ctx.fillStyle = "#8FCFC0";
        ctx.font = 'bold 9px var(--font-geist-mono, "JetBrains Mono", monospace)';
        ctx.textAlign = "center";
        const textY = n.pos === "top" ? n.y - 10 : n.y + 16;
        ctx.fillText(n.label, n.x, textY);
        ctx.restore();
      });

      // 8. Subtle crosshair at cursor if inside canvas
      if (mouseRef.current) {
        const mx = mouseRef.current.x;
        const my = mouseRef.current.y;
        ctx.save();
        ctx.strokeStyle = "rgba(143, 207, 192, 0.25)";
        ctx.lineWidth = 1;

        ctx.beginPath();
        ctx.moveTo(mx - 8, my);
        ctx.lineTo(mx + 8, my);
        ctx.moveTo(mx, my - 8);
        ctx.lineTo(mx, my + 8);
        ctx.stroke();
        ctx.restore();
      }

      ctx.restore();

      if (!reducedMotion) {
        animFrameRef.current = requestAnimationFrame(render);
      }
    }

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [onCoordinateChange]);

  return (
    <canvas
      ref={canvasRef}
      className="routex-canvas-bg"
      aria-hidden="true"
    />
  );
}
