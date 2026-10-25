import { ArrowRight, ArrowUpRight } from "lucide-react";
import BlurText from "@/components/BlurText";
import { ButtonLink } from "@/components/ui/button";
import { EVENT_NAME, GITHUB_URL } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Clay, type ClayName } from "./clay";

/** Clay objects floating around the mascot. Positions are % of the stage. */
const FLOATERS: {
  name: ClayName;
  size: number;
  className: string;
  tilt: string;
  delay: string;
  mobile?: boolean;
}[] = [
  { name: "loafer", size: 170, className: "left-[1%] top-[30%] sm:left-[4%] sm:top-[22%]", tilt: "-8deg", delay: "0s", mobile: true },
  { name: "phone", size: 120, className: "left-[20%] top-[2%]", tilt: "6deg", delay: "-2.2s" },
  { name: "coins", size: 120, className: "left-[2%] bottom-[2%] sm:left-[15%] sm:bottom-[4%]", tilt: "4deg", delay: "-1.1s", mobile: true },
  { name: "padlock", size: 130, className: "right-[1%] top-[26%] sm:right-[6%] sm:top-[16%]", tilt: "8deg", delay: "-3s", mobile: true },
  { name: "bag", size: 120, className: "right-[20%] top-[0%]", tilt: "-5deg", delay: "-0.6s" },
  { name: "receipt", size: 140, className: "right-[1%] bottom-[0%] sm:right-[14%] sm:bottom-[2%]", tilt: "-6deg", delay: "-1.8s", mobile: true },
];

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative overflow-hidden px-4 pt-6 pb-16 sm:px-6 sm:pt-10 sm:pb-24">
      <div className="mx-auto max-w-6xl">
        {/* Stage: mascot in the middle, clay objects drifting around it */}
        <div className="relative mx-auto h-[300px] max-w-5xl sm:h-[420px]">
          {FLOATERS.map((f) => (
            <div
              key={f.name}
              aria-hidden
              className={cn(
                "absolute animate-[float_7s_ease-in-out_infinite] will-change-transform",
                f.className,
                !f.mobile && "hidden md:block",
              )}
              style={{ ["--tilt" as string]: f.tilt, animationDelay: f.delay }}
            >
              <Clay name={f.name} size={f.size} decorative className="size-[72px] sm:size-auto" />
            </div>
          ))}
          <div className="absolute inset-x-0 bottom-0 mx-auto w-[260px] sm:w-[400px]">
            <Clay name="mascot" size={400} priority className="h-auto w-full" />
          </div>
        </div>

        <div className="relative mx-auto mt-2 max-w-3xl text-center">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-card px-3 py-1 text-[11px] font-medium tracking-[0.18em] text-muted uppercase ring-1 ring-line">
            <span className="size-1.5 rounded-full bg-accent" aria-hidden />
            Built for {EVENT_NAME}
          </p>
          <h1 id="hero-title" className="font-display text-[44px] leading-[0.95] font-semibold tracking-[-0.045em] text-balance text-ink sm:text-7xl">
            <BlurText
              text="Sowo dey sell while you sleep."
              animateBy="words"
              direction="bottom"
              trigger="load"
              delay={90}
              className="justify-center"
            />
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
