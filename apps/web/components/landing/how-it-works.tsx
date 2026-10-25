import { Clay, type ClayName } from "./clay";
import { Reveal } from "./reveal";

const STEPS: { pose: ClayName; title: string; body: string }[] = [
  {
    pose: "wave",
    title: "Buyer messages",
    body: "In Pidgin or English, at any hour. Sowo answers in seconds with real prices and stock.",
  },
  {
    pose: "haggle",
    title: "Sowo haggles to your floor",
    body: "You set the lowest price for each item. Sowo counters in steps and never goes below it.",
  },
  {
    pose: "coin",
    title: "Payment is verified",
    body: "Sowo sends a Paystack link. The order counts when Paystack confirms it, not when a screenshot arrives.",
  },
  {
    pose: "pack",
    title: "You pack",
    body: "You get an alert with the item, size and address. Pack it, send it, done.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-20 bg-card px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium text-accent-strong">How it works</p>
          <h2
            id="how-title"
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
          >
            From &ldquo;how much?&rdquo; to &ldquo;pack am&rdquo;, without you typing a word.
          </h2>
        </Reveal>

        <ol className="mt-16 grid gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <li key={step.title}>
              <Reveal delay={i * 110} className="flex flex-col items-center text-center">
                <div className="grid aspect-square w-full max-w-[240px] place-items-center rounded-[2rem] bg-paper">
                  <Clay name={step.pose} size={240} className="h-auto w-full" />
                </div>
                <p className="mt-6 font-mono text-xs text-muted">0{i + 1}</p>
                <h3 className="mt-1 font-display text-xl font-semibold tracking-[-0.02em]">{step.title}</h3>
                <p className="mt-2 max-w-[30ch] text-[15px] leading-relaxed text-muted">{step.body}</p>
              </Reveal>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
