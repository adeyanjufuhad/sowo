"use client";

import type { Message } from "@sowo/shared";
import { Bot, ChevronDown, Server } from "lucide-react";
import { watTime } from "@/lib/format";
import { summarizeToolCall } from "@/lib/tool-calls";
import { USING_MOCK } from "@/lib/api";

interface Turn {
  reply: Message;
  /** The buyer message Sowo was answering, if any. */
  prompt?: Message;
}

function turnsFrom(messages: Message[]): Turn[] {
  const turns: Turn[] = [];
  let lastBuyer: Message | undefined;
  for (const message of messages) {
    if (message.sender === "BUYER") lastBuyer = message;
    if (message.sender === "AI") turns.push({ reply: message, prompt: lastBuyer });
  }
  return turns.reverse(); // newest first
}

export function ToolPanel({ messages }: { messages: Message[] }) {
  const turns = turnsFrom(messages);

  return (
    <section aria-labelledby="tools-title" className="flex h-full flex-col">
      <div className="border-b border-line px-5 py-4">
        <h2 id="tools-title" className="font-display text-lg font-semibold tracking-[-0.02em]">
          Under the hood
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-muted">
          For every reply: the tool the model chose and its input, then the output the server computed. The floor price
          never appears here, because the model never sees it.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-wash px-2.5 py-1 text-accent-strong">
            <Bot aria-hidden className="size-3.5" strokeWidth={1.75} /> Model chose
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-night px-2.5 py-1 text-paper">
            <Server aria-hidden className="size-3.5" strokeWidth={1.75} /> Server decided
          </span>
        </div>
        {USING_MOCK ? (
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Demo mode: a scripted stand-in plays Qwen3&apos;s part so this runs offline. It calls the same tools, and
            the server logic is the same.
          </p>
        ) : null}
      </div>

      <ol aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {turns.length === 0 ? (
          <li className="rounded-2xl border border-dashed border-line px-4 py-8 text-center text-sm text-muted">
            Send a message to see what the model decides and what the server decides.
          </li>
        ) : null}

        {turns.map(({ reply, prompt }) => {
          const isReceipt = !reply.toolCalls && reply.body.includes("Receipt");
          return (
            <li key={reply.id} className="rounded-2xl bg-card p-4 ring-1 ring-line">
              <p className="flex items-baseline justify-between gap-3 text-xs text-muted">
                <span className="truncate">
                  {prompt && !isReceipt ? <>Reply to &ldquo;{prompt.body}&rdquo;</> : isReceipt ? "Payment event" : "Reply"}
                </span>
                <time dateTime={reply.createdAt} className="shrink-0 font-mono">
                  {watTime(reply.createdAt)}
                </time>
              </p>

              {reply.toolCalls?.length ? (
                <div className="mt-3 space-y-2.5">
                  {reply.toolCalls.map((call, i) => {
                    const summary = summarizeToolCall(call);
                    return (
                      <div key={i} className="overflow-hidden rounded-xl ring-1 ring-line">
                        <p className="bg-paper px-3 py-2 font-mono text-[13px] font-medium">{summary.tool}</p>
                        <dl className="text-[13px]">
                          <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2 sm:grid-cols-[7.5rem_minmax(0,1fr)] bg-accent-wash/60 px-3 py-2">
                            <dt className="flex items-center gap-1.5 text-accent-strong">
                              <Bot aria-hidden className="size-3.5" strokeWidth={1.75} /> Model chose
                            </dt>
                            <dd className="font-mono break-words">{summary.model}</dd>
                          </div>
                          <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2 sm:grid-cols-[7.5rem_minmax(0,1fr)] bg-night px-3 py-2 text-paper">
                            <dt className="flex items-center gap-1.5 text-mustard">
                              <Server aria-hidden className="size-3.5" strokeWidth={1.75} /> Server decided
                            </dt>
                            <dd className="font-mono break-words text-[#ffb59c]">{summary.server}</dd>
                          </div>
                        </dl>
                        <details className="group border-t border-line">
                          <summary className="flex cursor-pointer list-none items-center gap-1 px-3 py-1.5 text-xs text-muted hover:text-ink">
                            <ChevronDown aria-hidden className="size-3.5 transition-transform group-open:rotate-180" />
                            Raw JSON
                          </summary>
                          <pre className="max-h-64 overflow-auto bg-paper px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-soft">
                            {JSON.stringify({ input: call.input, output: call.output }, null, 2)}
                          </pre>
                        </details>
                      </div>
                    );
                  })}
                </div>
              ) : isReceipt ? (
                <div className="mt-3 rounded-xl bg-night px-3 py-2.5 font-mono text-[13px] text-paper">
                  <p className="text-mustard">paystack webhook</p>
                  <p className="text-[#ffb59c]">signature verified · amount matches · order PAID</p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted">No tool call: Sowo answered directly.</p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
