"use client";

import LogoLoop from "@/components/LogoLoop";

// Plain-text names of the open tools Sowo is built on. Not endorsements or customer logos.
const STACK = [
  "Qwen3",
  "Ollama",
  "WhatsApp Cloud API",
  "Paystack",
  "PostgreSQL",
  "Next.js",
  "TypeScript",
  "Tailwind CSS",
  "shadcn/ui",
  "React Bits",
];

export function BuiltWith() {
  return (
    <LogoLoop
      logos={STACK.map((name) => ({
        node: (
          <span className="font-display text-xl font-semibold tracking-[-0.03em] whitespace-nowrap text-ink/70 sm:text-2xl">
            {name}
          </span>
        ),
        title: name,
      }))}
      speed={45}
      gap={56}
      logoHeight={32}
      pauseOnHover
      fadeOut
      fadeOutColor="#fffdf9"
      ariaLabel="Open tools Sowo is built with"
    />
  );
}
