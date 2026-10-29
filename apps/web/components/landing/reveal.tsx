"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Direction = "up" | "down" | "left" | "right" | "none";

/** Fades content in as it scrolls into view. Without JS it shows immediately (see layout.tsx). */
export function Reveal({
  children,
  className,
  delay = 0,
  direction = "up",
  distance = 24,
  scale = 1,
  blur = 6,
  once = true,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  direction?: Direction;
  distance?: number;
  scale?: number;
  blur?: number;
  once?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        // Also reveal anything already scrolled past, e.g. after a fast scroll or an anchor jump.
        if (entry.isIntersecting || entry.boundingClientRect.top < 0) {
          setShown(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setShown(false);
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [once]);

  const x = direction === "left" ? -distance : direction === "right" ? distance : 0;
  const y = direction === "up" ? distance : direction === "down" ? -distance : 0;

  return (
    <div
      ref={ref}
      data-reveal
      style={{
        transitionDelay: `${delay}ms`,
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : `translate3d(${x}px, ${y}px, 0) scale(${scale})`,
        filter: shown || blur === 0 ? "none" : `blur(${blur}px)`,
      }}
      className={cn(
        "transition-[opacity,transform,filter] duration-[900ms] ease-(--ease-smooth) will-change-transform",
        className,
      )}
    >
      {children}
    </div>
  );
}
