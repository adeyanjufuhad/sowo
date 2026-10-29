import { EngineIllustration } from "./engine-illustration";
import { Reveal } from "./reveal";
import { ScrollFloat } from "./scroll-float";

export function EngineSection() {
  return (
    <section aria-labelledby="engine-title" className="px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="mx-auto max-w-6xl">
        <Reveal className="grid gap-6 md:grid-cols-[1.1fr_1fr] md:items-end">
          <div>
            <p className="text-sm font-medium text-accent-strong">Under the hood</p>
            <ScrollFloat
              id="engine-title"
              text="Every message runs through the same rules."
              delay={120}
              className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
            />
          </div>
          <div>
            <p className="max-w-[48ch] text-base leading-relaxed text-ink-soft">
              The AI reads the buyer and picks a tool. Your floor price, stock and delivery fees are enforced in code, so
              no clever message can talk it into a price you didn&apos;t set.
            </p>
          </div>
        </Reveal>

        <Reveal delay={120} className="mt-10">
          {/* Wider than the card on phones so the tape text stays legible; cropped at the edges */}
          <div className="overflow-hidden rounded-[2rem] bg-paper-deep/60 py-6 ring-1 ring-line sm:py-10">
            <div className="-mx-[35%] sm:mx-0">
              <EngineIllustration />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
