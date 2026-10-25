"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Fades content up once it scrolls into view. Without JS it shows immediately (see layout.tsx). */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Also reveal anything already scrolled past, e.g. after a fast scroll or an anchor jump.
        if (entry && (entry.isIntersecting || entry.boundingClientRect.top < 0)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      data-reveal
      style={{ transitionDelay: `${delay}ms` }}
      className={cn(
        "transition-[opacity,transform,filter] duration-[900ms] ease-(--ease-smooth)",
        shown ? "translate-y-0 opacity-100 blur-none" : "translate-y-6 opacity-0 blur-[6px]",
        className,
      )}
    >
      {children}
    </div>
  );
}
