import { BadgeCheck, EyeOff, Hand } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LanguageRotator } from "./language-rotator";
import { Reveal } from "./reveal";

function Tile({
  title,
  body,
  children,
  className,
  delay = 0,
}: {
  title: ReactNode;
  body: string;
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <Reveal delay={delay} className={cn("flex flex-col", className)}>
      <div className="flex-1 rounded-[2rem] bg-paper-deep/70 p-1.5 ring-1 ring-line">
        <div className="flex h-full min-h-[240px] items-center justify-center rounded-[calc(2rem-0.375rem)] bg-card p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] sm:p-8">
          {children}
        </div>
      </div>
      <h3 className="mt-5 font-display text-xl font-semibold tracking-[-0.02em]">{title}</h3>
      <p className="mt-1.5 max-w-[46ch] text-[15px] leading-relaxed text-muted">{body}</p>
    </Reveal>
  );
}

/** Price ladder: base, counter, agreed, with the vendor-only floor beneath. */
function PriceLadder() {
  const steps = [
    { label: "Asking", price: "₦45,000", tone: "text-ink" },
    { label: "Buyer offers", price: "₦35,000", tone: "text-muted line-through decoration-accent/60" },
    { label: "Sowo counters", price: "₦43,000", tone: "text-ink" },
    { label: "Deal", price: "₦41,000", tone: "text-accent-strong" },
  ];
  return (
    <div className="w-full max-w-sm">
      <ol className="space-y-2">
        {steps.map((s) => (
          <li key={s.label} className="flex items-center justify-between rounded-xl bg-paper px-4 py-2.5">
            <span className="text-sm text-muted">{s.label}</span>
            <span className={cn("font-mono text-sm font-medium", s.tone)}>{s.price}</span>
          </li>
        ))}
      </ol>
      <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-dashed border-accent/50 px-4 py-2.5">
        <span className="flex items-center gap-2 text-sm whitespace-nowrap text-muted">
          <EyeOff aria-hidden className="size-4" strokeWidth={1.75} /> Your floor
        </span>
        <span className="text-right text-xs text-muted">Only you see it</span>
      </div>
    </div>
  );
}

function WebhookCard() {
  return (
    <div className="w-full max-w-sm rounded-2xl bg-night p-5 font-mono text-[13px] text-paper/90">
      <p className="text-mustard">charge.success</p>
      <dl className="mt-3 space-y-1.5">
        {[
          ["reference", "SW-1043"],
          ["signature", "verified"],
          ["amount", "₦43,500 = order total"],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4">
            <dt className="text-paper/50">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 flex items-center gap-2 border-t border-paper/10 pt-3 text-[#ffb59c]">
        <BadgeCheck aria-hidden className="size-4" strokeWidth={1.75} /> Order #1043 PAID · pack now
      </p>
    </div>
  );
}

function TakeoverCard() {
  return (
    <div className="w-full max-w-sm space-y-2.5">
      {[
        { name: "Funke A.", text: "Can I exchange it for 39?", status: "Needs you", hot: true },
        { name: "Blessing E.", text: "Sizes 38, 39, 39, 40, 41, 42", status: "You're replying", hot: false },
        { name: "Seun B.", text: "Lekki Phase 1", status: "Sowo active", hot: false },
      ].map((c) => (
        <div
          key={c.name}
          className={cn(
            "flex items-center justify-between gap-3 rounded-xl px-4 py-3",
            c.hot ? "bg-accent-wash ring-1 ring-accent/40" : "bg-paper",
          )}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">{c.name}</p>
            <p className="truncate text-xs text-muted">{c.text}</p>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium",
              c.hot ? "bg-accent-strong text-white" : "bg-card text-ink-soft ring-1 ring-line",
            )}
          >
            {c.status}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Features() {
  return (
    <section id="features" aria-labelledby="features-title" className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-medium text-accent-strong">Features</p>
          <h2
            id="features-title"
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
          >
            Made for how people actually buy here.
          </h2>
        </Reveal>

        <div className="mt-14 grid gap-x-6 gap-y-12 md:grid-cols-5">
          <Tile
            className="md:col-span-3"
            title="Haggling down to your floor"
            body="Set a price and a floor for each item. Sowo concedes in steps, holds firm at the floor, and never reveals it to the buyer or to the model."
          >
            <PriceLadder />
          </Tile>
          <Tile
            className="md:col-span-2"
            delay={100}
            title="Verified payments"
            body="Paystack confirms every order by webhook. No packing for fake transfer alerts."
          >
            <WebhookCard />
          </Tile>
          <Tile
            className="md:col-span-2"
            title="Pause AI, take over"
            body="Jump into any chat with one tap and Sowo goes quiet. It flags exchanges, complaints and bulk orders for you."
          >
            <TakeoverCard />
          </Tile>
          <Tile
            className="md:col-span-3"
            delay={100}
            title={
              <>
                Replies in <LanguageRotator />
              </>
            }
            body="Buyers write how they talk. Sowo understands “Abeg do am 35k” and answers in the same register."
          >
            <div className="w-full max-w-md space-y-2.5 text-[15px]">
              <p className="w-fit max-w-[85%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 ring-1 ring-line">
                Abeg you get white sneakers size 44?
              </p>
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent-wash px-4 py-2.5">
                Size 44 don finish o. Na size 41 remain, ₦38,000.
              </p>
              <p className="w-fit max-w-[85%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 ring-1 ring-line">
                Can you do 50k on the brown boots?
              </p>
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent-wash px-4 py-2.5">
                Done! ₦50,000 for the size 43 boots. Where should we deliver?
              </p>
            </div>
          </Tile>
        </div>

        <p className="mt-10 flex items-center gap-2 text-sm text-muted">
          <Hand aria-hidden className="size-4" strokeWidth={1.75} />
          Sowo never sends money, issues refunds or changes prices on its own.
        </p>
      </div>
    </section>
  );
}
