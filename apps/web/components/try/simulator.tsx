"use client";

import { formatNaira, type Conversation, type Message, type Order, type RequestPaymentCall } from "@sowo/shared";
import { ArrowUp, CheckCheck, Landmark, LayoutDashboard, LockKeyhole, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { api, ApiRequestError } from "@/lib/api";
import { watTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ToolPanel } from "./tool-panel";

const CONVERSATION_KEY = "sowo.try.conversation";
const POLL_MS = 3000;

/** The headline haggle, in order. Each chip disappears once sent. */
const SCRIPT = ["How much for the black loafers?", "Na size 43", "Abeg do am 35k", "Make it 41 na", "I dey Ikeja"];

function readStoredId(): string | null {
  try {
    return window.localStorage.getItem(CONVERSATION_KEY);
  } catch {
    return null;
  }
}

function storeId(id: string | null) {
  try {
    if (id) window.localStorage.setItem(CONVERSATION_KEY, id);
    else window.localStorage.removeItem(CONVERSATION_KEY);
  } catch {
    // the chat still works, it just won't survive a reload
  }
}

function paymentCall(message: Message): RequestPaymentCall | undefined {
  return message.toolCalls?.find((c): c is RequestPaymentCall => c.tool === "request_payment");
}

function suggestions(messages: Message[], orders: Map<string, Order>): string[] {
  const sent = new Set(messages.filter((m) => m.sender === "BUYER").map((m) => m.body.trim().toLowerCase()));
  const chips = SCRIPT.filter((line) => !sent.has(line.toLowerCase()));
  const linkSent = messages.some((m) => paymentCall(m));
  const paid = [...orders.values()].some((o) => o.paymentStatus === "PAID");
  if (linkSent && !paid) chips.push("I don transfer, check am");
  if (paid) chips.push("Thank you!", "Can I exchange them for size 44?");
  if (!linkSent) chips.push("You get white sneakers size 44?");
  return chips.slice(0, 5);
}

export function Simulator() {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [orders, setOrders] = useState<Map<string, Order>>(new Map());
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paying, setPaying] = useState<string | null>(null);
  const [receiptFor, setReceiptFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"chat" | "tools">("chat");
  const threadRef = useRef<HTMLDivElement>(null);
  const pendingSeq = useRef(0);
  const inputId = useId();

  const refreshOrders = useCallback(async (conversationId: string) => {
    const { orders: all } = await api.listOrders();
    const mine = all.filter((o) => o.conversationId === conversationId && o.paymentReference);
    setOrders(new Map(mine.map((o) => [o.paymentReference as string, o])));
  }, []);

  // Restore the last chat after a reload.
  useEffect(() => {
    const id = readStoredId();
    if (!id) return;
    api
      .listMessages(id)
      .then(async (res) => {
        setConversation(res.conversation);
        setMessages(res.messages);
        await refreshOrders(id);
      })
      .catch(() => storeId(null));
  }, [refreshOrders]);

  const waitingOnAda = [...orders.values()].some((o) => o.paymentMethod === "MANUAL" && o.paymentStatus === "PENDING");

  // Poll so replies Ada sends from the dashboard show up here, and so does her tapping Mark paid.
  useEffect(() => {
    if (!conversation || sending || paying || receiptFor) return;
    const timer = window.setInterval(async () => {
      try {
        const res = await api.listMessages(conversation.id);
        setConversation(res.conversation);
        setMessages((prev) => (res.messages.length !== prev.length ? res.messages : prev));
        if (waitingOnAda) await refreshOrders(conversation.id);
      } catch {
        // keep the current view; the next poll may succeed
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [conversation, sending, paying, receiptFor, waitingOnAda, refreshOrders]);

  // Keep the newest message in view.
  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending]);

  async function send(text: string) {
    const body = text.trim();
    if (!body || sending) return;
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: Message = {
      id: `pending-${(pendingSeq.current += 1)}`,
      conversationId: conversation?.id ?? "pending",
      sender: "BUYER",
      body,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    try {
      const res = await api.sendSimulatorMessage({ conversationId: conversation?.id, body });
      setConversation(res.conversation);
      storeId(res.conversation.id);
      setMessages((prev) => [...prev.filter((m) => m.id !== optimistic.id), ...res.messages]);
      if (res.messages.some(paymentCall)) await refreshOrders(res.conversation.id);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setDraft(body);
      setError(err instanceof ApiRequestError ? err.message : "Couldn't send that. Check your connection and try again.");
    } finally {
      setSending(false);
    }
  }

  async function pay(reference: string, outcome: "SUCCESS" | "FAILED") {
    setPaying(reference);
    setError(null);
    try {
      const res = await api.simulatePayment({ reference, outcome });
      setOrders((prev) => new Map(prev).set(reference, res.order));
      setMessages((prev) => [...prev, ...res.messages]);
      const fresh = await api.listMessages(res.order.conversationId ?? "");
      setConversation(fresh.conversation);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Payment simulation failed. Try again.");
    } finally {
      setPaying(null);
    }
  }

  async function sendReceipt(reference: string) {
    setReceiptFor(reference);
    setError(null);
    try {
      const res = await api.sendSimulatorReceipt({ reference });
      setOrders((prev) => new Map(prev).set(reference, res.order));
      setMessages((prev) => [...prev, ...res.messages]);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't send the receipt. Try again.");
    } finally {
      setReceiptFor(null);
    }
  }

  function newChat() {
    storeId(null);
    setConversation(null);
    setMessages([]);
    setOrders(new Map());
    setError(null);
    setDraft("");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  const chips = suggestions(messages, orders);
  const status = conversation?.status;
  const typing = sending && (!status || status === "AI_ACTIVE" || status === "CLOSED");
  const toolCount = messages.filter((m) => m.sender === "AI").length;

  const chat = (
    <div className="flex h-full min-h-0 flex-col">
      {/* Chat header */}
      <div className="flex items-center justify-between gap-3 border-b border-line bg-card px-4 py-3">
        <div className="flex items-center gap-3">
          <span aria-hidden className="grid size-10 place-items-center rounded-full bg-accent-wash font-display text-sm font-bold text-accent-strong">
            AF
          </span>
          <div>
            <p className="text-sm font-semibold">Ada&apos;s Footwear</p>
            <p className="text-xs text-muted">{status === "HUMAN_TAKEOVER" ? "Ada is typing herself" : "Usually replies in seconds"}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={newChat}
          className="inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
        >
          <RotateCcw aria-hidden className="size-3.5" strokeWidth={2} /> New chat
        </button>
      </div>

      {/* Thread */}
      <div ref={threadRef} className="min-h-0 flex-1 overflow-y-auto bg-paper px-3 py-4 sm:px-4">
        {messages.length === 0 ? (
          <div className="mx-auto mt-6 max-w-[30ch] text-center">
            <p className="font-display text-xl font-semibold tracking-[-0.02em]">You&apos;re the buyer.</p>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Ask Ada&apos;s Footwear about a pair of shoes and try to haggle. Tap a suggestion below or type in Pidgin
              or English.
            </p>
          </div>
        ) : null}

        <ol aria-label="Conversation" aria-live="polite" className="flex flex-col gap-2.5">
          {messages.map((message) => {
            const mine = message.sender === "BUYER";
            const vendor = message.sender === "VENDOR";
            const payment = paymentCall(message);
            const order = payment ? orders.get(payment.output.reference) : undefined;
            // The payment card below replaces the "Pay here: <link>" sentence.
            const body = payment ? message.body.replace(/\s*Pay[^.\n]*?:\s*https?:\/\/\S+/i, "") : message.body;
            return (
              <li key={message.id} className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
                <div
                  className={cn(
                    "max-w-[85%] animate-[bubble-in_320ms_var(--ease-smooth)_both] rounded-2xl px-3.5 py-2 text-[15px] leading-snug whitespace-pre-line",
                    mine ? "rounded-br-md bg-accent-strong text-white" : "rounded-bl-md bg-card text-ink ring-1 ring-line",
                  )}
                >
                  <span className="sr-only">{mine ? "You: " : vendor ? "" : "Sowo: "}</span>
                  {vendor ? <span className="mb-0.5 block text-xs font-semibold text-accent-strong">Ada</span> : null}
                  {body}
                  <span className={cn("mt-1 flex items-center justify-end gap-1 text-[11px]", mine ? "text-white/70" : "text-muted")}>
                    {watTime(message.createdAt)}
                    {mine ? <CheckCheck aria-hidden className="size-3.5" strokeWidth={2} /> : null}
                  </span>
                </div>

                {payment?.output.method === "MANUAL" && payment.output.bank ? (
                  <div className="mt-2 w-[85%] max-w-xs rounded-2xl bg-card p-3.5 ring-1 ring-line">
                    <p className="flex items-center gap-1.5 text-xs text-muted">
                      <Landmark aria-hidden className="size-3.5" strokeWidth={1.75} /> Bank transfer to Ada
                    </p>
                    <p className="mt-1 font-display text-2xl font-semibold tracking-[-0.03em]">
                      {formatNaira(payment.output.amountKobo)}
                    </p>
                    <dl className="mt-2 space-y-0.5 text-sm">
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Bank</dt>
                        <dd>{payment.output.bank.bankName}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Name</dt>
                        <dd>{payment.output.bank.accountName}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Account</dt>
                        <dd className="font-mono tracking-wide">{payment.output.bank.accountNumber}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Narration</dt>
                        <dd className="font-mono text-xs">{payment.output.reference}</dd>
                      </div>
                    </dl>
                    {order?.paymentStatus === "PAID" ? (
                      <p className="mt-3 rounded-lg bg-accent-wash px-3 py-2 text-sm font-medium text-accent-strong">
                        Paid. Ada confirmed the transfer.
                      </p>
                    ) : order?.receiptReportedAt ? (
                      <p className="mt-3 rounded-lg bg-paper-deep px-3 py-2 text-sm text-ink-soft">
                        Receipt sent. Waiting for Ada to confirm it in her dashboard.
                      </p>
                    ) : order?.paymentStatus === "PENDING" ? (
                      <button
                        type="button"
                        disabled={receiptFor !== null}
                        onClick={() => sendReceipt(payment.output.reference)}
                        className="mt-3 h-9 w-full rounded-full bg-accent-strong px-3 text-sm font-medium text-white transition-[transform,background-color] hover:bg-[#a33515] active:scale-[0.98] disabled:opacity-60"
                      >
                        {receiptFor === payment.output.reference ? "Sending…" : "I've sent the transfer"}
                      </button>
                    ) : (
                      <p className="mt-3 rounded-lg bg-paper-deep px-3 py-2 text-sm text-ink-soft">This order is closed.</p>
                    )}
                  </div>
                ) : payment ? (
                  <div className="mt-2 w-[85%] max-w-xs rounded-2xl bg-card p-3.5 ring-1 ring-line">
                    <p className="flex items-center gap-1.5 text-xs text-muted">
                      <LockKeyhole aria-hidden className="size-3.5" strokeWidth={1.75} /> Paystack · test mode
                    </p>
                    <p className="mt-1 font-display text-2xl font-semibold tracking-[-0.03em]">
                      {formatNaira(payment.output.amountKobo)}
                    </p>
                    <p className="font-mono text-[11px] text-muted">{payment.output.reference}</p>
                    {order?.paymentStatus === "PAID" ? (
                      <p className="mt-3 rounded-lg bg-accent-wash px-3 py-2 text-sm font-medium text-accent-strong">Paid. Confirmed by webhook.</p>
                    ) : order?.paymentStatus === "FAILED" ? (
                      <p className="mt-3 rounded-lg bg-paper-deep px-3 py-2 text-sm text-ink-soft">Payment failed. Nothing was charged.</p>
                    ) : (
                      <div className="mt-3 flex gap-2">
                        <button
                          type="button"
                          disabled={paying !== null}
                          onClick={() => pay(payment.output.reference, "SUCCESS")}
                          className="h-9 flex-1 rounded-full bg-accent-strong px-3 text-sm font-medium text-white transition-[transform,background-color] hover:bg-[#a33515] active:scale-[0.98] disabled:opacity-60"
                        >
                          {paying === payment.output.reference ? "Paying…" : `Pay ${formatNaira(payment.output.amountKobo)}`}
                        </button>
                        <button
                          type="button"
                          disabled={paying !== null}
                          onClick={() => pay(payment.output.reference, "FAILED")}
                          className="h-9 rounded-full px-3 text-xs font-medium text-ink-soft ring-1 ring-line transition-colors hover:bg-paper-deep disabled:opacity-60"
                        >
                          Fail it
                        </button>
                      </div>
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}

          {typing ? (
            <li aria-hidden className="flex">
              <span className="flex gap-1 rounded-2xl rounded-bl-md bg-card px-4 py-3 ring-1 ring-line">
                {[0, 1, 2].map((d) => (
                  <span
                    key={d}
                    className="size-1.5 animate-[typing_1s_ease-in-out_infinite] rounded-full bg-accent-strong"
                    style={{ animationDelay: `${d * 150}ms` }}
                  />
                ))}
              </span>
            </li>
          ) : null}
        </ol>

        {status === "NEEDS_ATTENTION" || status === "HUMAN_TAKEOVER" ? (
          <div className="mx-auto mt-4 max-w-sm rounded-2xl bg-card p-4 text-center text-sm ring-1 ring-line">
            <p className="font-medium">
              {status === "NEEDS_ATTENTION" ? "Sowo has handed this chat to Ada." : "Ada has taken over. Sowo is paused."}
            </p>
            <Link
              href="/dashboard"
              className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-accent-strong underline-offset-4 hover:underline"
            >
              <LayoutDashboard aria-hidden className="size-4" strokeWidth={1.75} /> Reply as Ada in the dashboard
            </Link>
          </div>
        ) : null}
      </div>

      {/* Composer */}
      <div className="border-t border-line bg-card px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        {chips.length ? (
          <div className="-mx-3 mb-2.5 flex gap-2 overflow-x-auto px-3 pb-1 [scrollbar-width:none]">
            {chips.map((chip) => (
              <button
                key={chip}
                type="button"
                disabled={sending}
                onClick={() => send(chip)}
                className="shrink-0 rounded-full bg-paper px-3 py-1.5 text-sm whitespace-nowrap text-ink ring-1 ring-line transition-colors hover:bg-accent-wash hover:ring-accent/40 disabled:opacity-50"
              >
                {chip}
              </button>
            ))}
          </div>
        ) : null}
        {error ? (
          <p role="alert" className="mb-2 rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
            {error}
          </p>
        ) : null}
        <form onSubmit={onSubmit} className="flex items-center gap-2">
          <label htmlFor={inputId} className="sr-only">
            Message Ada&apos;s Footwear
          </label>
          <input
            id={inputId}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message…"
            autoComplete="off"
            className="h-11 min-w-0 flex-1 rounded-full bg-paper px-4 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={!draft.trim() || sending}
            className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-strong text-white transition-[transform,opacity] active:scale-95 disabled:opacity-40"
          >
            <ArrowUp aria-hidden className="size-5" strokeWidth={2} />
          </button>
        </form>
      </div>
    </div>
  );

  return (
    <div className="mx-auto grid w-full max-w-7xl grid-cols-[minmax(0,1fr)] gap-0 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)] lg:gap-6 lg:px-6 lg:py-8">
      {/* Phone-width tabs */}
      <div role="tablist" aria-label="View" className="sticky top-14 z-30 flex gap-1 border-b border-line bg-paper px-4 py-2 lg:hidden">
        {(
          [
            ["chat", "Chat"],
            ["tools", `Under the hood${toolCount ? ` (${toolCount})` : ""}`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cn(
              "flex-1 rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
              tab === key ? "bg-ink text-paper" : "text-ink-soft hover:bg-paper-deep",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Phone */}
      <div
        className={cn(
          "h-[calc(100dvh-7.5rem)] lg:block lg:h-[min(780px,calc(100dvh-8rem))] lg:overflow-hidden lg:rounded-[2.25rem] lg:bg-ink lg:p-2 lg:shadow-[0_30px_60px_-30px_rgba(31,26,23,0.5)]",
          tab === "chat" ? "block" : "hidden",
        )}
      >
        <div className="h-full overflow-hidden lg:rounded-[1.8rem]">{chat}</div>
      </div>

      {/* Tool calls */}
      <div
        className={cn(
          "min-h-[60vh] lg:block lg:h-[min(780px,calc(100dvh-8rem))] lg:overflow-hidden lg:rounded-[2rem] lg:bg-paper-deep/60 lg:ring-1 lg:ring-line",
          tab === "tools" ? "block" : "hidden",
        )}
      >
        <ToolPanel messages={messages} />
      </div>
    </div>
  );
}
