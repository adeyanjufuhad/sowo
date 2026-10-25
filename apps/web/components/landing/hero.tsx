import { ArrowRight, ArrowUpRight } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { GITHUB_URL } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Clay, type ClayName } from "./clay";

const HEADLINE = "Sowo dey sell while you sleep.";

/** Clay objects floating around the mascot. Positions are % of the stage. */
const FLOATERS: {
  name: ClayName;
  size: number;
  className: string;
  tilt: string;
  delay: string;
  mobile?: boolean;
}[] = [
  { name: "loafer", size: 132, className: "left-[0%] top-[14%] sm:left-[3%] sm:top-[20%]", tilt: "-8deg", delay: "0s", mobile: true },
  { name: "phone", size: 96, className: "left-[19%] top-[0%]", tilt: "6deg", delay: "-2.2s" },
  { name: "coins", size: 100, className: "left-[4%] bottom-[4%] sm:left-[14%] sm:bottom-[6%]", tilt: "4deg", delay: "-1.1s", mobile: true },
  { name: "padlock", size: 96, className: "right-[2%] top-[12%] sm:right-[6%] sm:top-[16%]", tilt: "8deg", delay: "-3s", mobile: true },
  { name: "bag", size: 100, className: "right-[19%] top-[0%]", tilt: "-5deg", delay: "-0.6s" },
  { name: "receipt", size: 110, className: "right-[3%] bottom-[2%] sm:right-[14%] sm:bottom-[4%]", tilt: "-6deg", delay: "-1.8s", mobile: true },
];

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative overflow-hidden px-4 pt-4 pb-16 sm:px-6 sm:pt-10 sm:pb-24">
      <div className="mx-auto max-w-6xl">
        {/* Stage: mascot in the middle, clay objects drifting around it */}
        <div className="relative mx-auto h-[230px] max-w-5xl sm:h-[360px]">
          <div className="absolute inset-x-0 bottom-0 mx-auto w-[190px] sm:w-[300px]">
            <span
              aria-hidden
              className="absolute inset-x-[12%] -bottom-2 h-6 rounded-[50%] bg-[radial-gradient(closest-side,rgba(110,62,30,0.22),transparent)]"
            />
            <Clay name="mascot" size={300} priority className="relative h-auto w-full" />
          </div>
          {FLOATERS.map((f) => (
            <div
              key={f.name}
              aria-hidden
              className={cn(
                "absolute animate-[float_7s_ease-in-out_infinite] will-change-transform",
                f.className,
                !f.mobile && "hidden md:block",
              )}
              style={{ ["--tilt" as string]: f.tilt, ["--size" as string]: `${f.size}px`, animationDelay: f.delay }}
            >
              <Clay name={f.name} size={f.size} decorative className="size-[60px] sm:size-(--size)" />
            </div>
          ))}
        </div>

        <div className="relative mx-auto mt-6 max-w-3xl text-center">
          <h1 id="hero-title" className="mx-auto max-w-[8.6em] font-display text-[44px] leading-[0.95] font-semibold tracking-[-0.045em] text-balance text-ink sm:text-7xl">
            {/* Pure CSS word-by-word entrance: visible even before (or without) JavaScript */}
            {HEADLINE.split(" ").map((word, i) => (
              <span key={i}>
                <span
                  className="inline-block animate-[word-in_800ms_var(--ease-smooth)_both]"
                  style={{ animationDelay: `${120 + i * 90}ms` }}
                >
                  {word}
                </span>{" "}
              </span>
            ))}
          </h1>
          <p className="mx-auto mt-6 max-w-[56ch] text-base leading-relaxed text-ink-soft text-pretty sm:text-lg">
            An AI sales assistant for Nigerian vendors on WhatsApp. It answers buyers in seconds, haggles down to the
            floor price you set, sends a Paystack link and tells you when to pack.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <ButtonLink href="/try" size="lg" icon={<ArrowRight className="size-4" strokeWidth={2} />}>
              Try the live demo
            </ButtonLink>
            <ButtonLink
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              variant="secondary"
              size="lg"
              icon={<ArrowUpRight className="size-4" strokeWidth={2} />}
            >
              View on GitHub
            </ButtonLink>
          </div>
        </div>
      </div>
    </section>
  );
}
