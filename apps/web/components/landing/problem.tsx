import { Clock3, Repeat2, ShieldAlert } from "lucide-react";
import { Reveal } from "./reveal";

const PAINS = [
  {
    icon: Clock3,
    title: "Slow replies lose sales",
    body: "A buyer who asks at 11pm and hears back at 9am has already bought from the next stall.",
  },
  {
    icon: Repeat2,
    title: "Haggling eats the day",
    body: "The same price question fifty times, then a back-and-forth with every single buyer.",
  },
  {
    icon: ShieldAlert,
    title: "Fake alerts cost stock",
    body: "A doctored transfer screenshot looks real enough, and the shoes are gone before the bank app loads.",
  },
];

export function Problem() {
  return (
    <section aria-labelledby="problem-title" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-[1.15fr_1fr] md:gap-20">
        <Reveal className="md:sticky md:top-28 md:self-start">
          <p className="text-sm font-medium text-accent-strong">The problem</p>
          <h2
            id="problem-title"
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-[56px]"
          >
            Selling on WhatsApp means never putting the phone down.
          </h2>
          <p className="mt-6 max-w-[50ch] text-base leading-relaxed text-ink-soft sm:text-lg">
            Across Nigeria, vendors run whole shops from a chat app. Every sale is typed by hand: answer the price,
            haggle, share account details, wait for the alert, confirm the address. Step away for an hour and the buyer
            moves on.
          </p>
        </Reveal>

        <ul className="divide-y divide-line border-y border-line">
          {PAINS.map((pain, i) => (
            <li key={pain.title}>
              <Reveal delay={i * 110} className="flex gap-5 py-8">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-wash">
                  <pain.icon aria-hidden className="size-5 text-accent-strong" strokeWidth={1.75} />
                </span>
                <div>
                  <h3 className="font-display text-xl font-semibold tracking-[-0.02em]">{pain.title}</h3>
                  <p className="mt-2 max-w-[42ch] text-[15px] leading-relaxed text-muted">{pain.body}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
