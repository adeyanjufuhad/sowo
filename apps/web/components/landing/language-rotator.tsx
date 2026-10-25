"use client";

import RotatingText from "@/components/RotatingText";

export function LanguageRotator() {
  return (
    <>
      <span className="sr-only">Pidgin and English</span>
      <RotatingText
        texts={["Pidgin", "English"]}
        rotationInterval={2200}
        effect="slide"
        mainClassName="inline-flex overflow-hidden rounded-lg bg-accent-wash px-2 align-bottom text-accent-strong"
        staggerDuration={0.02}
        aria-hidden
      />
    </>
  );
}
