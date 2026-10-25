import { BuiltWith } from "./built-with";

// Product facts, not usage statistics: each is a property of how Sowo works.
const FACTS = [
  { value: "24/7", label: "Replies at 2pm and at 2am" },
  { value: "₦0", label: "Sold below the floor you set" },
  { value: "2", label: "Languages: Pidgin and English" },
  { value: "MIT", label: "Licensed. Read every line." },
];

export function StackStrip() {
  return (
    <section aria-label="What Sowo is built on" className="px-4 sm:px-6">
      <div className="mx-auto max-w-6xl rounded-[2rem] bg-paper-deep/70 p-1.5 ring-1 ring-line">
        <div className="rounded-[calc(2rem-0.375rem)] bg-card shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
          <p className="pt-7 text-center text-xs font-medium tracking-[0.18em] text-muted uppercase">
            Built in the open with
          </p>
          <div className="py-6">
            <BuiltWith />
          </div>
          <dl className="grid grid-cols-2 border-t border-line md:grid-cols-4">
            {FACTS.map((fact, i) => (
              <div
                key={fact.label}
                className={[
                  "px-6 py-6 sm:px-8",
                  i % 2 === 1 ? "border-l border-line" : "",
                  i >= 2 ? "border-t border-line md:border-t-0" : "",
                  i === 2 ? "md:border-l" : "",
                ].join(" ")}
              >
                <dt className="sr-only">{fact.label}</dt>
                <dd className="font-display text-4xl font-semibold tracking-[-0.04em] text-ink sm:text-5xl">
                  {fact.value}
                </dd>
                <dd className="mt-1 text-sm text-muted">{fact.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
