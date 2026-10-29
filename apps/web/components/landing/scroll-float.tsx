"use client";

import { useEffect, useRef, useState } from "react";

/**
 * React Bits' ScrollFloat, rebuilt without GSAP: words rise out of the line,
 * one after another, when the heading reaches the viewport.
 */
export function ScrollFloat({
  text,
  id,
  className,
  delay = 0,
  stagger = 45,
  distance = 0.55,
}: {
  text: string;
  id?: string;
  className?: string;
  delay?: number;
  stagger?: number;
  /** How far below the line each word starts, in em. */
  distance?: number;
}) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry && (entry.isIntersecting || entry.boundingClientRect.top < 0)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <h2 ref={ref} id={id} aria-label={text} className={className}>
      <span aria-hidden="true">
        {text.split(" ").map((word, i) => (
          <span key={`${word}-${i}`}>
            <span
              data-reveal
              className="inline-block will-change-transform transition-[opacity,transform,filter] duration-[850ms] ease-(--ease-spring)"
              style={{
                transitionDelay: `${delay + i * stagger}ms`,
                opacity: shown ? 1 : 0,
                transform: shown ? "none" : `translate3d(0, ${distance}em, 0) rotate(2.5deg)`,
                filter: shown ? "none" : "blur(5px)",
              }}
            >
              {word}
            </span>{" "}
          </span>
        ))}
      </span>
    </h2>
  );
}
