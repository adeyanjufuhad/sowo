import type { Message } from "@sowo/shared";
import { Bot, Server } from "lucide-react";
import { ChatReplay } from "./chat-replay";
import { Reveal } from "./reveal";
import { ScrollFloat } from "./scroll-float";

export function ReplaySection({ messages }: { messages: Message[] }) {
  return (
    <section id="replay" aria-labelledby="replay-title" className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto grid max-w-6xl items-start gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
        <Reveal className="lg:sticky lg:top-28">
          <p className="text-sm font-medium text-accent-strong">A real sale, replayed</p>
          <ScrollFloat
            id="replay-title"
            text="Watch Sowo sell a pair of loafers."
            delay={120}
            className="mt-3 font-display text-4xl leading-[1.02] font-semibold tracking-[-0.04em] text-balance sm:text-5xl"
          />
          <p className="mt-6 max-w-[48ch] text-base leading-relaxed text-ink-soft sm:text-lg">
            Kelechi wants black leather loafers in size 43. He offers ₦35,000, Sowo counters, they settle on ₦41,000,
            and the ₦43,500 payment clears with delivery to Ikeja.
          </p>

          <dl className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <div className="rounded-2xl bg-card p-5 ring-1 ring-line">
              <dt className="flex items-center gap-2 text-sm font-semibold">
                <Bot aria-hidden className="size-4 text-accent-strong" strokeWidth={1.75} />
                Qwen3 decides
              </dt>
              <dd className="mt-2 text-sm leading-relaxed text-muted">
                What the buyer means, which tool to call, and how to say the reply.
              </dd>
            </div>
            <div className="rounded-2xl bg-night p-5 text-paper">
              <dt className="flex items-center gap-2 text-sm font-semibold">
                <Server aria-hidden className="size-4 text-mustard" strokeWidth={1.75} />
                The server decides
              </dt>
              <dd className="mt-2 text-sm leading-relaxed text-paper/70">
                Every price, counter, total and stock change. The floor price never reaches the model.
              </dd>
            </div>
          </dl>
        </Reveal>

        <Reveal delay={120}>
          <ChatReplay messages={messages} />
        </Reveal>
      </div>
    </section>
  );
}
