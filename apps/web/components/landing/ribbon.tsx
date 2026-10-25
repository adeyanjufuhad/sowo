"use client";

import LogoLoop from "@/components/LogoLoop";

const PHRASES = ["Abeg do am 35k", "Make it 41 na", "Payment confirmed", "Sowo dey sell while you sleep"];

/** A slightly tilted terracotta band of real buyer phrases, scrolling across the page. */
export function Ribbon() {
  return (
    <div aria-hidden className="relative overflow-hidden py-10">
      {/* Wider than the viewport so the tilted band's ends stay off-screen */}
      <div className="-mx-[6vw] -rotate-2 bg-accent-strong py-4 shadow-[0_18px_40px_-20px_rgba(184,60,25,0.6)]">
        <LogoLoop
          logos={PHRASES.map((phrase) => ({
            node: (
              <span className="flex items-center gap-10 font-display text-2xl font-semibold tracking-[-0.02em] whitespace-nowrap text-white sm:text-4xl">
                {phrase}
                <span className="text-mustard">✦</span>
              </span>
            ),
            title: phrase,
          }))}
          speed={60}
          gap={40}
          logoHeight={40}
          ariaLabel="Buyer phrases"
        />
      </div>
    </div>
  );
}
