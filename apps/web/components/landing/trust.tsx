import { BadgeCheck, Code2, EyeOff, Hand } from "lucide-react";
import { Reveal } from "./reveal";

const PILLARS = [
  {
    icon: EyeOff,
    title: "Your floor stays secret",
    body: "Prices, counters and stock are decided in code. The AI never sees your floor price, and no message can talk it down.",
  },
  {
    icon: BadgeCheck,
    title: "Money decides, not screenshots",
    body: "An order is paid when the transfer is in your account or Paystack's webhook confirms it. Sowo never takes a buyer's word for it.",
  },
  {
    icon: Hand,
    title: "Take over in one tap",
    body: "Pause Sowo mid-chat and answer the buyer yourself. It stays quiet until you switch it back on.",
  },
  {
    icon: Code2,
    title: "Open source, MIT",
    body: "Frontend, backend and the rules between them are public, so you can read exactly how a price is decided.",
  },
];

const BADGES = ["Qwen3", "WhatsApp Cloud API", "Bank transfer", "Paystack", "MIT licensed"];

export function Trust() {
  return (
    <section id="trust" aria-labelledby="trust-title" className="scroll-mt-20 px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="mx-auto max-w-6xl rounded-[2.5rem] bg-card px-6 py-16 ring-1 ring-line sm:px-12 sm:py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium text-accent-strong">Trust and control</p>
          <h2
            id="trust-title"
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
          >
            Sowo sells. You stay in charge.
          </h2>
        </Reveal>

        <ul className="mt-10 flex flex-wrap justify-center gap-2" aria-label="What Sowo runs on">
          {BADGES.map((badge) => (
            <li key={badge} className="rounded-full bg-paper px-3.5 py-1.5 font-mono text-xs text-ink-soft ring-1 ring-line">
              {badge}
            </li>
          ))}
        </ul>

        <div className="mt-14 grid gap-x-10 gap-y-10 sm:grid-cols-2">
          {PILLARS.map((pillar, i) => (
            <Reveal key={pillar.title} delay={(i % 2) * 100} className="flex gap-4">
              <pillar.icon aria-hidden className="mt-1 size-5 shrink-0 text-accent-strong" strokeWidth={1.75} />
              <div>
                <h3 className="font-display text-lg font-semibold tracking-[-0.02em]">{pillar.title}</h3>
                <p className="mt-1.5 max-w-[44ch] text-[15px] leading-relaxed text-muted">{pillar.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
