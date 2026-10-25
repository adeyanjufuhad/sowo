"use client";

import CurvedLoop from "@/components/CurvedLoop";

/** A terracotta ribbon of real buyer phrases, curving across the page. */
export function Ribbon() {
  return (
    <div aria-hidden className="relative -my-6 overflow-hidden py-2 text-accent">
      <CurvedLoop
        marqueeText="Abeg do am 35k ✦ Make it 41 na ✦ Payment confirmed ✦ Sowo dey sell while you sleep"
        separator="✦"
        speed={1.2}
        curveAmount={140}
        interactive={false}
        fontSize={56}
        fontWeight={700}
        letterSpacing={-1}
        color="var(--accent)"
        className="font-display"
      />
    </div>
  );
}
