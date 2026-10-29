"use client";

import { useEffect, useRef } from "react";

type Spark = { x: number; y: number; start: number; lines: number[] };

const SPARKS = 8;
const RADIUS = 22;
const SIZE = 11;
const DURATION = 420;

/** React Bits' ClickSpark: a short burst of lines at every click, drawn on one shared canvas. */
export function ClickSpark() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const context = canvas.getContext("2d");
    if (!context) return undefined;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;

    const sparks: Spark[] = [];
    let width = 0;
    let height = 0;
    let frame = 0;

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      frame = 0;
      context.clearRect(0, 0, width, height);
      context.strokeStyle = "#e4572e";
      context.lineWidth = 2;
      context.lineCap = "round";
      for (let i = sparks.length - 1; i >= 0; i--) {
        const spark = sparks[i]!;
        const t = Math.min(1, (now - spark.start) / DURATION);
        if (t >= 1) {
          sparks.splice(i, 1);
          continue;
        }
        const eased = t * (2 - t);
        const from = eased * RADIUS;
        const to = from + SIZE * (1 - t * 0.55);
        context.globalAlpha = 1 - eased;
        for (const angle of spark.lines) {
          const cos = Math.cos(angle);
          const sin = Math.sin(angle);
          context.beginPath();
          context.moveTo(spark.x + cos * from, spark.y + sin * from);
          context.lineTo(spark.x + cos * to, spark.y + sin * to);
          context.stroke();
        }
      }
      context.globalAlpha = 1;
      if (sparks.length > 0) frame = requestAnimationFrame(draw);
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      sparks.push({
        x: event.clientX,
        y: event.clientY,
        start: performance.now(),
        lines: Array.from({ length: SPARKS }, (_, i) => (i * 2 * Math.PI) / SPARKS),
      });
      if (!frame) frame = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-[60]" />;
}
