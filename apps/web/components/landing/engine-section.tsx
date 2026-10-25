import { ArrowUpRight } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { GITHUB_URL } from "@/lib/site";
import { EngineIllustration } from "./engine-illustration";
import { Reveal } from "./reveal";

export function EngineSection() {
  return (
    <section aria-labelledby="engine-title" className="px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="mx-auto max-w-6xl">
        <Reveal className="grid gap-6 md:grid-cols-[1.1fr_1fr] md:items-end">
          <div>
            <p className="text-sm font-medium text-accent-strong">Under the hood</p>
            <h2
              id="engine-title"
              className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
            >
              Every message runs through the same rules.
            </h2>
          </div>
          <div>
            <p className="max-w-[48ch] text-base leading-relaxed text-ink-soft">
              Qwen3 reads the buyer and picks a tool. The floor-price engine, stock and Paystack checks run in code, so a
              clever buyer can&apos;t talk the model into a lower price.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <ButtonLink
                href={`${GITHUB_URL}/blob/main/docs/api-contract.md`}
                target="_blank"
                rel="noreferrer"
                variant="secondary"
                size="sm"
              >
                Read the API contract
              </ButtonLink>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-9 items-center gap-1 rounded-full px-3 text-sm whitespace-nowrap text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
              >
                Source on GitHub <ArrowUpRight aria-hidden className="size-3.5" strokeWidth={1.75} />
              </a>
            </div>
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
