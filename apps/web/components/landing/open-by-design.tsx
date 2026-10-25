import { Code2, Cpu, Lock, Scale } from "lucide-react";
import { Reveal } from "./reveal";

const PILLARS = [
  {
    icon: Cpu,
    title: "Qwen3, open weights",
    body: "The model runs on your own machine through Ollama. Qwen3 is released under Apache 2.0.",
  },
  {
    icon: Lock,
    title: "The model never touches money",
    body: "It reads messages and picks tools. Prices, totals and stock are decided in code you can read.",
  },
  {
    icon: Code2,
    title: "Open source, MIT",
    body: "Frontend, backend and the API contract between them are public. Fork it and run it for your own shop.",
  },
  {
    icon: Scale,
    title: "No closed-model APIs",
    body: "No calls to OpenAI or Anthropic anywhere in the product. Your buyers' chats stay with you.",
  },
];

const BADGES = ["Qwen3", "Apache 2.0", "Ollama", "MIT", "TypeScript", "Paystack test mode"];

export function OpenByDesign() {
  return (
    <section id="open" aria-labelledby="open-title" className="scroll-mt-20 px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="mx-auto max-w-6xl rounded-[2.5rem] bg-card px-6 py-16 ring-1 ring-line sm:px-12 sm:py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium text-accent-strong">Open by design</p>
          <h2
            id="open-title"
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
          >
            Built on a model you can run, in code you can read.
          </h2>
        </Reveal>

        <ul className="mt-10 flex flex-wrap justify-center gap-2" aria-label="Licences and tools">
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
