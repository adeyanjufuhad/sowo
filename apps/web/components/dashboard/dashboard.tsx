"use client";

import { formatNaira } from "@sowo/shared";
import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, resetDemoData, USING_MOCK } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ChatList, ChatThread } from "./chats";
import { OrdersView } from "./orders";
import { ProductsView } from "./products";
import { usePoll } from "./use-poll";

type Tab = "chats" | "orders" | "products";
const TABS: Tab[] = ["chats", "orders", "products"];

async function loadAll() {
  const [{ conversations }, { orders }, { products }] = await Promise.all([
    api.listConversations(),
    api.listOrders(),
    api.listProducts(),
  ]);
  return { conversations, orders, products, at: Date.now() };
}

function ResetButton({ onReset }: { onReset: () => void }) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = window.setTimeout(() => setArmed(false), 3000);
    return () => window.clearTimeout(timer);
  }, [armed]);

  return (
    <button
      type="button"
      onClick={() => {
        if (!armed) return setArmed(true);
        setArmed(false);
        onReset();
      }}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors",
        armed ? "bg-accent-strong text-white" : "text-ink-soft ring-1 ring-line hover:bg-paper-deep",
      )}
    >
      <RotateCcw aria-hidden className="size-3.5" strokeWidth={2} />
      {armed ? "Tap again to reset" : "Reset demo data"}
    </button>
  );
}

export function Dashboard() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tabParam = params.get("tab");
  const tab: Tab = TABS.includes(tabParam as Tab) ? (tabParam as Tab) : "chats";
  const chatId = params.get("chat");

  const { data, error, refresh } = usePoll(loadAll, "dashboard");

  function navigate(next: { tab?: Tab; chat?: string | null }) {
    const query = new URLSearchParams(params.toString());
    if (next.tab) query.set("tab", next.tab);
    if (next.chat === null) query.delete("chat");
    else if (next.chat) query.set("chat", next.chat);
    if (query.get("tab") === "chats") query.delete("tab");
    const qs = query.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const conversations = data?.conversations ?? [];
  const orders = data?.orders ?? [];
  const now = data?.at ?? 0;
  const selected = conversations.find((c) => c.id === chatId) ?? null;

  const needsYou = conversations.filter((c) => c.status === "NEEDS_ATTENTION").length;
  const active = conversations.filter((c) => c.status === "AI_ACTIVE" || c.status === "HUMAN_TAKEOVER").length;
  const toPack = orders.filter((o) => o.paymentStatus === "PAID" && o.fulfillmentStatus === "PACKAGING").length;
  const paidKobo = orders.filter((o) => o.paymentStatus === "PAID").reduce((sum, o) => sum + o.totalKobo, 0);

  const stats = [
    { label: "Need you", value: String(needsYou), hot: needsYou > 0, go: () => navigate({ tab: "chats" }) },
    { label: "Active chats", value: String(active), go: () => navigate({ tab: "chats" }) },
    { label: "To pack", value: String(toPack), hot: toPack > 0, go: () => navigate({ tab: "orders", chat: null }) },
    { label: "Paid", value: formatNaira(paidKobo), go: () => navigate({ tab: "orders", chat: null }) },
  ];

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "chats", label: "Chats", count: needsYou || undefined },
    { key: "orders", label: "Orders" },
    { key: "products", label: "Products" },
  ];

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 sm:py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted">Ada&apos;s Footwear</p>
          <h1 className="font-display text-3xl font-semibold tracking-[-0.03em]">Dashboard</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-muted" title="Refreshes every 3 seconds">
            <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-[#2f8f5b]" /> Live
          </span>
          {USING_MOCK ? (
            <ResetButton
              onReset={() => {
                resetDemoData();
                navigate({ chat: null });
                void refresh();
              }}
            />
          ) : null}
        </div>
      </div>

      {/* Summary, computed from the data below */}
      <dl className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
        {stats.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={s.go}
            className={cn(
              "rounded-2xl px-4 py-3 text-left ring-1 transition-colors",
              s.hot ? "bg-accent-strong text-white ring-accent-strong" : "bg-card ring-line hover:bg-paper-deep",
            )}
          >
            <dt className={cn("text-xs", s.hot ? "text-white/80" : "text-muted")}>{s.label}</dt>
            <dd className="mt-0.5 font-display text-2xl font-semibold tracking-[-0.03em]">{data ? s.value : "·"}</dd>
          </button>
        ))}
      </dl>

      {error ? (
        <p role="alert" className="mt-4 rounded-xl bg-accent-wash px-4 py-3 text-sm text-accent-strong">
          {error}
        </p>
      ) : null}

      {/* Tabs */}
      <div role="tablist" aria-label="Dashboard sections" className="mt-6 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            aria-controls={`panel-${t.key}`}
            onClick={() => navigate({ tab: t.key })}
            className={cn(
              "-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
              tab === t.key ? "border-accent-strong text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t.label}
            {t.count ? (
              <span className="rounded-full bg-accent-strong px-1.5 py-px text-[11px] text-white" aria-label={`${t.count} need you`}>
                {t.count}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <div id={`panel-${tab}`} role="tabpanel" className="mt-4">
        {data === null ? (
          <div aria-hidden className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="block h-16 animate-pulse rounded-2xl bg-paper-deep" />
            ))}
          </div>
        ) : tab === "chats" ? (
          <div className="overflow-hidden rounded-2xl bg-card ring-1 ring-line lg:grid lg:h-[calc(100dvh-20rem)] lg:min-h-[520px] lg:grid-cols-[360px_minmax(0,1fr)]">
            <div className={cn("overflow-y-auto lg:border-r lg:border-line", selected ? "hidden lg:block" : "block")}>
              <ChatList
                conversations={conversations}
                selectedId={selected?.id ?? null}
                onSelect={(id) => navigate({ chat: id })}
                now={now}
              />
            </div>
            {/* On phones an open chat fills the screen under the header, like a messaging app */}
            <div
              className={cn(
                "min-h-0",
                selected ? "fixed inset-x-0 top-14 bottom-0 z-30 bg-card lg:static lg:z-auto lg:block" : "hidden lg:block",
              )}
            >
              {selected ? (
                <ChatThread
                  key={selected.id}
                  conversation={selected}
                  orders={orders}
                  onBack={() => navigate({ chat: null })}
                  onChanged={() => void refresh()}
                />
              ) : (
                <div className="grid h-full place-items-center px-6 text-center text-sm text-muted">
                  <p>
                    Pick a chat to read it and reply.
                    <br />
                    Haggle as a buyer in the{" "}
                    <Link href="/try" className="font-medium text-accent-strong underline-offset-4 hover:underline">
                      buyer simulator
                    </Link>{" "}
                    and watch it land here.
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : tab === "orders" ? (
          <OrdersView orders={orders} now={now} />
        ) : (
          <ProductsView products={data.products} />
        )}
      </div>
    </div>
  );
}
