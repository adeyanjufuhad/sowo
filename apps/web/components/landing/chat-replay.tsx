"use client";

import type { Message } from "@sowo/shared";
import { CheckCheck, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { watTime } from "@/lib/format";
import { summarizeToolCall } from "@/lib/tool-calls";

const BUYER_PAUSE_MS = 1300;
const TYPING_MS = 1100;

function isReceipt(message: Message) {
  return message.sender === "AI" && !message.toolCalls && message.body.includes("Receipt");
}

/** Show a link as a pill instead of a raw URL. */
function Body({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/\S+)/g);
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <span key={i} className="my-1 inline-flex items-center rounded-full bg-accent-strong px-3 py-1 text-xs font-medium text-white">
            Pay with Paystack (test)
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function ChatReplay({ messages }: { messages: Message[] }) {
  const [shown, setShown] = useState(0);
  const [showTools, setShowTools] = useState(false);
  const [started, setStarted] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const switchId = useId();
  const done = shown >= messages.length;
  const next = messages[shown];
  // Sowo "types" while the next message due is one of its own.
  const typing = started && !done && next?.sender !== "BUYER";

  // Start when the chat scrolls into view; with reduced motion, show everything at once.
  useEffect(() => {
    const element = rootRef.current;
    if (!element) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        if (reduceMotion) setShown(messages.length);
        else setStarted(true);
        observer.disconnect();
      },
      { threshold: 0.2 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [messages.length]);

  // Advance one message at a time: a pause before the buyer speaks, a typing beat before Sowo does.
  useEffect(() => {
    if (!started || !next) return;
    const wait = next.sender === "BUYER" ? (shown === 0 ? 300 : BUYER_PAUSE_MS) : TYPING_MS;
    const timer = window.setTimeout(() => setShown((n) => n + 1), wait);
    return () => window.clearTimeout(timer);
  }, [started, shown, next]);

  const replay = useCallback(() => {
    setShown(0);
    setStarted(true);
  }, []);

  return (
    <div ref={rootRef} className="rounded-[2rem] bg-paper-deep/80 p-1.5 ring-1 ring-line">
      <div className="overflow-hidden rounded-[calc(2rem-0.375rem)] bg-card shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
        {/* Chat header */}
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div className="flex items-center gap-3">
            <span aria-hidden className="grid size-10 place-items-center rounded-full bg-accent-wash font-display text-sm font-bold text-accent-strong">
              AF
            </span>
            <div>
              <p className="text-sm font-semibold">Ada&apos;s Footwear</p>
              <p className="text-xs text-muted">Sowo is replying for Ada</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor={switchId} className="text-xs font-medium whitespace-nowrap text-ink-soft">
              Tool calls
            </label>
            <button
              id={switchId}
              type="button"
              role="switch"
              aria-checked={showTools}
              onClick={() => setShowTools((v) => !v)}
              className={cn(
                "relative h-6 w-11 rounded-full transition-colors duration-300",
                showTools ? "bg-accent-strong" : "bg-line",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform duration-300 ease-(--ease-spring)",
                  showTools && "translate-x-5",
                )}
              />
            </button>
          </div>
        </div>

        {/* Thread. Every message stays in the DOM (readable by screen readers); unplayed ones are just invisible. */}
        <ol aria-label="Replay of the loafers sale" className="flex flex-col gap-3 bg-paper/60 px-4 py-6 sm:px-6">
          {messages.map((message, i) => {
            const visible = i < shown;
            const isTypingSlot = typing && i === shown;
            const fromBuyer = message.sender === "BUYER";
            return (
              <li
                key={message.id}
                className={cn("relative flex flex-col", fromBuyer ? "items-start" : "items-end")}
              >
                {isTypingSlot ? (
                  <span
                    aria-hidden
                    className="absolute top-0 right-0 flex gap-1 rounded-2xl rounded-br-md bg-accent-wash px-4 py-3"
                  >
                    {[0, 1, 2].map((d) => (
                      <span
                        key={d}
                        className="size-1.5 animate-[typing_1s_ease-in-out_infinite] rounded-full bg-accent-strong"
                        style={{ animationDelay: `${d * 150}ms` }}
                      />
                    ))}
                  </span>
                ) : null}
                <div
                  className={cn(
                    "flex max-w-[85%] flex-col",
                    fromBuyer ? "items-start" : "items-end",
                    visible ? "animate-[bubble-in_420ms_var(--ease-smooth)_both]" : "opacity-0",
                  )}
                >
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-2.5 text-[15px] leading-snug whitespace-pre-line",
                      fromBuyer
                        ? "rounded-bl-md bg-white text-ink ring-1 ring-line"
                        : "rounded-br-md bg-accent-wash text-ink",
                    )}
                  >
                    <span className="sr-only">{fromBuyer ? "Kelechi: " : "Sowo: "}</span>
                    <Body text={message.body} />
                    <span className="mt-1 flex items-center justify-end gap-1 text-[11px] text-muted">
                      {watTime(message.createdAt)}
                      {!fromBuyer ? <CheckCheck aria-hidden className="size-3.5" strokeWidth={2} /> : null}
                    </span>
                  </div>

                  {showTools && message.toolCalls?.length ? (
                    <div className="mt-2 w-full max-w-md space-y-1.5">
                      {message.toolCalls.map((call, j) => {
                        const summary = summarizeToolCall(call);
                        return (
                          <div key={j} className="rounded-xl bg-night px-3.5 py-2.5 font-mono text-[12px] leading-relaxed text-paper/90">
                            <p className="text-mustard">{summary.tool}</p>
                            <p>
                              <span className="text-paper/50">model  </span>
                              {summary.model}
                            </p>
                            <p>
                              <span className="text-paper/50">server </span>
                              <span className="text-[#ffb59c]">{summary.server}</span>
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}

                  {showTools && isReceipt(message) ? (
                    <div className="mt-2 w-full max-w-md rounded-xl bg-night px-3.5 py-2.5 font-mono text-[12px] leading-relaxed text-paper/90">
                      <p className="text-mustard">paystack webhook</p>
                      <p>
                        <span className="text-paper/50">server </span>
                        <span className="text-[#ffb59c]">signature verified · amount matches · PAID</span>
                      </p>
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
          <p className="text-xs text-muted">
            {showTools ? "Model picks the tool. Server decides every number." : "Turn on tool calls to see who decides what."}
          </p>
          <button
            type="button"
            onClick={replay}
            disabled={!done}
            className="inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink disabled:opacity-40"
          >
            <RotateCcw aria-hidden className="size-3.5" strokeWidth={2} />
            Replay
          </button>
        </div>
      </div>
    </div>
  );
}
