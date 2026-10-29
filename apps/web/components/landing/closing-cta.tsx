import { ArrowRight, Store } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { Clay } from "./clay";
import { Reveal } from "./reveal";
import { ScrollFloat } from "./scroll-float";
import { StarBorder } from "./star-border";

export function ClosingCta() {
  return (
    <section aria-labelledby="cta-title" className="px-4 pb-14 sm:px-6 sm:pb-16">
      <div className="mx-auto grid max-w-6xl items-center gap-8 md:grid-cols-[1fr_1.1fr]">
        <Reveal className="mx-auto w-full max-w-[300px]">
          <Clay name="night" size={300} className="h-auto w-full" />
        </Reveal>
        <Reveal delay={120} className="text-center md:text-left">
          <ScrollFloat
            id="cta-title"
            text="Close the shop. Sowo keeps selling."
            className="font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-6xl"
          />
          <p className="mx-auto mt-5 max-w-[46ch] text-base leading-relaxed text-ink-soft sm:text-lg md:mx-0">
            Try the demo shop as a buyer, then open the vendor dashboard and watch the order land.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row md:justify-start">
            <StarBorder speed={5}>
              <ButtonLink href="/signup" size="lg" icon={<ArrowRight className="size-4" strokeWidth={2} />}>
                Start selling
              </ButtonLink>
            </StarBorder>
            <ButtonLink href="/try" variant="secondary" size="lg" icon={<Store className="size-4" strokeWidth={1.75} />}>
              Visit a demo shop
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
