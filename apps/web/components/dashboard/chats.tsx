"use client";

import { formatNaira, type Conversation, type Order } from "@sowo/shared";
import { ArrowLeft, ArrowUp, Bot, ChevronDown, MessagesSquare, Package } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { api, ApiRequestError } from "@/lib/api";
import { initials, relativeTime, watTime } from "@/lib/format";
import { summarizeToolCall } from "@/lib/tool-calls";
import { cn } from "@/lib/utils";
import { ConversationBadge, FulfillmentBadge, PaymentBadge } from "./badges";
import { usePoll } from "./use-poll";

/** NEEDS_ATTENTION first, then newest. */
function sortChats(conversations: Conversation[]) {
  return [...conversations].sort((a, b) => {
    const urgent = Number(b.status === "NEEDS_ATTENTION") - Number(a.status === "NEEDS_ATTENTION");
    return urgent || b.lastMessageAt.localeCompare(a.lastMessageAt);
  });
}

export function ChatList({
  conversations,
  selectedId,
  onSelect,
  now,
}: {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  now: number;
}) {
  if (conversations.length === 0) {
    return (
      <div className="px-6 py-16 text-center text-sm text-muted">
        <MessagesSquare aria-hidden className="mx-auto mb-3 size-6" strokeWidth={1.5} />
        No chats yet. Start one from the buyer simulator.
      </div>
    );
  }
  return (
    <ul aria-label="Chats" className="divide-y divide-line">
      {sortChats(conversations).map((c) => {
        const urgent = c.status === "NEEDS_ATTENTION";
        const selected = c.id === selectedId;
        return (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => onSelect(c.id)}
              aria-current={selected ? "true" : undefined}
              className={cn(
                "flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors",
                selected ? "bg-paper-deep" : urgent ? "bg-accent-wash/70 hover:bg-accent-wash" : "hover:bg-paper",
                urgent && "shadow-[inset_3px_0_0_var(--accent-strong)]",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold",
                  urgent ? "bg-accent-strong text-white" : "bg-paper-deep text-ink-soft",
                )}
              >
                {initials(c.customerName)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-semibold">{c.customerName}</span>
                  <time dateTime={c.lastMessageAt} className="shrink-0 text-xs text-muted">
                    {relativeTime(c.lastMessageAt, now)}
                  </time>
                </span>
                <span className="mt-0.5 block truncate text-sm text-muted">{c.preview}</span>
                <span className="mt-2 flex flex-wrap items-center gap-1.5">
                  <ConversationBadge status={c.status} />
                  {c.platform === "SIMULATOR" ? (
                    <span className="rounded-full bg-paper px-2 py-0.5 text-[11px] text-muted ring-1 ring-line">Simulator</span>
                  ) : null}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function ChatThread({
  conversation,
  orders,
  onBack,
  onChanged,
}: {
  conversation: Conversation;
  orders: Order[];
  onBack: () => void;
  onChanged: () => void;
}) {
  const { data, error: loadError, refresh, setData } = usePoll(() => api.listMessages(conversation.id), conversation.id);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<"toggle" | "send" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();
  const listRef = useRef<HTMLOListElement>(null);

  // Prefer the freshest copy of the conversation (the poll) over the list's.
  const current = data?.conversation.id === conversation.id ? data.conversation : conversation;
  const messages = data?.conversation.id === conversation.id ? data.messages : [];
  const aiOn = current.status === "AI_ACTIVE" || current.status === "CLOSED";
  const order = orders.find((o) => o.conversationId === conversation.id);

  // Open at, and follow, the newest message.
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length]);

  async function toggleAi() {
    setBusy("toggle");
    setError(null);
    try {
      const res = aiOn ? await api.pauseConversation(current.id) : await api.resumeConversation(current.id);
      setData((prev) => (prev ? { ...prev, conversation: res.conversation } : prev));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't change that. Try again.");
    } finally {
      setBusy(null);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const body = draft.trim();
    if (!body) return;
    setBusy("send");
    setError(null);
    try {
      await api.sendVendorReply(current.id, body);
      setDraft("");
      await refresh();
      onChanged();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't send. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-label={`Chat with ${current.customerName}`} className="flex h-full min-h-0 flex-col">
      {/* Thread header */}
      <div className="flex items-center gap-3 border-b border-line bg-card px-3 py-3 sm:px-4">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to chats"
          className="grid size-9 shrink-0 place-items-center rounded-full text-ink-soft hover:bg-paper-deep lg:hidden"
        >
          <ArrowLeft aria-hidden className="size-5" strokeWidth={1.75} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{current.customerName}</p>
          <div className="mt-0.5">
            <ConversationBadge status={current.status} />
          </div>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm font-medium">
          <span className="hidden sm:inline">Sowo replies</span>
          <span className="sm:hidden">AI</span>
          <button
            type="button"
            role="switch"
            aria-checked={aiOn}
            aria-label={aiOn ? "Pause Sowo for this chat" : "Resume Sowo for this chat"}
            disabled={busy === "toggle"}
            onClick={toggleAi}
            className={cn(
              "relative h-7 w-12 rounded-full transition-colors duration-300 disabled:opacity-60",
              aiOn ? "bg-[#2f8f5b]" : "bg-line",
            )}
          >
            <span
              aria-hidden
              className={cn(
                "absolute top-0.5 left-0.5 size-6 rounded-full bg-white shadow transition-transform duration-300 ease-(--ease-spring)",
                aiOn && "translate-x-5",
              )}
            />
          </button>
        </label>
      </div>

      {/* Order linked to this chat */}
      {order ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-line bg-paper px-4 py-2.5 text-sm">
          <Package aria-hidden className="size-4 text-muted" strokeWidth={1.75} />
          <span className="font-medium">{order.id.replace("ord_", "Order #")}</span>
          <span className="text-muted">{order.items.map((i) => i.name).join(", ")}</span>
          <span className="font-mono">{formatNaira(order.totalKobo)}</span>
          <PaymentBadge status={order.paymentStatus} />
          {order.paymentStatus === "PAID" ? <FulfillmentBadge status={order.fulfillmentStatus} /> : null}
        </div>
      ) : null}

      {/* Messages */}
      <ol ref={listRef} aria-label="Messages" aria-live="polite" className="min-h-0 flex-1 space-y-2.5 overflow-y-auto bg-paper px-3 py-4 sm:px-5">
        {data === null && !loadError ? (
          <li className="space-y-2.5" aria-hidden>
            {[60, 45, 70].map((w, i) => (
              <span key={i} className={cn("block h-12 animate-pulse rounded-2xl bg-paper-deep", i % 2 ? "ml-auto" : "")} style={{ width: `${w}%` }} />
            ))}
          </li>
        ) : null}
        {messages.map((m) => {
          const fromBuyer = m.sender === "BUYER";
          return (
            <li key={m.id} className={cn("flex flex-col", fromBuyer ? "items-start" : "items-end")}>
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2 text-[15px] leading-snug whitespace-pre-line",
                  fromBuyer && "rounded-bl-md bg-card ring-1 ring-line",
                  m.sender === "AI" && "rounded-br-md bg-accent-wash",
                  m.sender === "VENDOR" && "rounded-br-md bg-accent-strong text-white",
                )}
              >
                <span className={cn("mb-0.5 block text-xs font-semibold", m.sender === "VENDOR" ? "text-white/80" : fromBuyer ? "text-muted" : "text-accent-strong")}>
                  {fromBuyer ? current.customerName : m.sender === "AI" ? "Sowo" : "You"}
                </span>
                {m.body}
                <span className={cn("mt-1 block text-right text-[11px]", m.sender === "VENDOR" ? "text-white/70" : "text-muted")}>
                  {watTime(m.createdAt)}
                </span>
              </div>
              {m.toolCalls?.length ? (
                <details className="group mt-1 max-w-[85%] text-xs text-muted">
                  <summary className="flex cursor-pointer list-none items-center justify-end gap-1 hover:text-ink">
                    <Bot aria-hidden className="size-3.5" strokeWidth={1.75} />
                    {m.toolCalls.length} tool call{m.toolCalls.length > 1 ? "s" : ""}
                    <ChevronDown aria-hidden className="size-3.5 transition-transform group-open:rotate-180" />
                  </summary>
                  <ul className="mt-1.5 space-y-1 rounded-xl bg-night p-2.5 font-mono text-[11px] text-paper/90">
                    {m.toolCalls.map((call, i) => {
                      const s = summarizeToolCall(call);
                      return (
                        <li key={i}>
                          <span className="text-mustard">{s.tool}</span> {s.model} <span className="text-paper/50">→</span>{" "}
                          <span className="text-[#ffb59c]">{s.server}</span>
                        </li>
                      );
                    })}
                  </ul>
                </details>
              ) : null}
            </li>
          );
        })}
      </ol>

      {/* Reply */}
      <form onSubmit={send} className="border-t border-line bg-card px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-4">
        {error || loadError ? (
          <p role="alert" className="mb-2 rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
            {error ?? loadError}
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          <label htmlFor={inputId} className="sr-only">
            Reply to {current.customerName} as Ada
          </label>
          <input
            id={inputId}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Reply as Ada…"
            autoComplete="off"
            className="h-11 min-w-0 flex-1 rounded-full bg-paper px-4 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong"
          />
          <button
            type="submit"
            aria-label="Send reply"
            disabled={!draft.trim() || busy === "send"}
            className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-strong text-white transition-[transform,opacity] active:scale-95 disabled:opacity-40"
          >
            <ArrowUp aria-hidden className="size-5" strokeWidth={2} />
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">
          {aiOn ? "Replying pauses Sowo for this chat until you switch it back on." : "Sowo is paused here. Switch it on to let it take over again."}
        </p>
      </form>
    </section>
  );
}
