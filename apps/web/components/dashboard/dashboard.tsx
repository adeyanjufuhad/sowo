"use client";

import { formatNaira } from "@sowo/shared";
import {
  ArrowUpRight,
  Bot,
  CircleAlert,
  MessageCircleMore,
  MessagesSquare,
  PackageCheck,
  PackageOpen,
  RotateCcw,
  ShoppingBag,
  Sparkles,
  Store,
  WalletCards,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import ShinyText from "@/components/ShinyText";
import SpotlightCard from "@/components/SpotlightCard";
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
        "inline-flex h-10 items-center gap-2 rounded-xl px-3.5 text-xs font-semibold transition-all",
        armed
          ? "bg-accent-strong text-white shadow-lg shadow-accent-strong/20"
          : "border border-line bg-card/80 text-ink-soft shadow-sm hover:border-ink-soft/25 hover:bg-card",
      )}
    >
      <RotateCcw aria-hidden className="size-3.5" strokeWidth={2} />
      {armed ? "Confirm reset" : "Reset demo"}
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
  const paidOrders = orders.filter((o) => o.paymentStatus === "PAID");
  const paidKobo = paidOrders.reduce((sum, o) => sum + o.totalKobo, 0);

  const stats: {
    label: string;
    value: string;
    detail: string;
    icon: LucideIcon;
    featured?: boolean;
    hot?: boolean;
    go: () => void;
  }[] = [
    {
      label: "Paid revenue",
      value: formatNaira(paidKobo),
      detail: `${paidOrders.length} paid order${paidOrders.length === 1 ? "" : "s"}`,
      icon: WalletCards,
      featured: true,
      go: () => navigate({ tab: "orders", chat: null }),
    },
    {
      label: "Need you",
      value: String(needsYou),
      detail: needsYou ? "Replies waiting" : "Inbox under control",
      icon: CircleAlert,
      hot: needsYou > 0,
      go: () => navigate({ tab: "chats" }),
    },
    {
      label: "Active chats",
      value: String(active),
      detail: `${conversations.length} conversation${conversations.length === 1 ? "" : "s"} total`,
      icon: MessageCircleMore,
      go: () => navigate({ tab: "chats" }),
    },
    {
      label: "Ready to pack",
      value: String(toPack),
      detail: toPack ? "Fulfilment needed" : "Nothing waiting",
      icon: PackageCheck,
      hot: toPack > 0,
      go: () => navigate({ tab: "orders", chat: null }),
    },
  ];

  const tabs: { key: Tab; label: string; icon: LucideIcon; count?: number }[] = [
    { key: "chats", label: "Conversations", icon: MessagesSquare, count: needsYou || undefined },
    { key: "orders", label: "Orders", icon: ShoppingBag },
    { key: "products", label: "Catalogue", icon: PackageOpen },
  ];

  const panelCopy = {
    chats: ["Customer conversations", "Follow every sale and step in whenever Sowo needs you."],
    orders: ["Orders & fulfilment", "Track payments and move paid orders out the door."],
    products: ["Your catalogue", "The prices and stock Sowo uses while negotiating with buyers."],
  }[tab];

  return (
    <div className="relative isolate min-h-[calc(100dvh-4rem)] overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_8%_0%,rgba(226,167,46,0.10),transparent_30%),radial-gradient(circle_at_92%_12%,rgba(184,60,25,0.08),transparent_28%)]" />
      <div aria-hidden className="pointer-events-none absolute top-28 -right-32 -z-10 size-96 rounded-full border border-accent/10" />

      <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <header className="dashboard-enter flex flex-wrap items-end justify-between gap-5">
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-muted uppercase">
              <span className="grid size-7 place-items-center rounded-lg bg-night text-paper shadow-sm">
                <Store aria-hidden className="size-3.5" />
              </span>
              Ada&apos;s Footwear
              <span className="h-3 w-px bg-line" />
              Vendor workspace
            </div>
            <h1 className="font-display text-[clamp(2rem,4vw,3.25rem)] leading-[1.02] font-semibold tracking-[-0.045em]">
              Your shop, at a glance.
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted sm:text-base">
              Sowo is handling the conversations. You stay in control of the sale.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#bfd8c8] bg-[#edf6f0]/80 px-3.5 text-xs font-semibold text-[#236442] shadow-sm">
              <span className="relative flex size-2" aria-hidden>
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-[#3b9365] opacity-50" />
                <span className="relative inline-flex size-2 rounded-full bg-[#2f8f5b]" />
              </span>
              Live workspace
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
            <Link
              href="/try"
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-night px-4 text-xs font-semibold text-white shadow-lg shadow-night/15 transition-all hover:-translate-y-0.5 hover:bg-night-soft"
            >
              Buyer simulator
              <ArrowUpRight aria-hidden className="size-4" />
            </Link>
          </div>
        </header>

        <div aria-label="Shop summary" className="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-10 lg:gap-4">
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <SpotlightCard
                key={stat.label}
                theme={stat.featured ? "dark" : "light"}
                spotlightColor={stat.featured ? "#f2b65b" : "#e4572e"}
                intensity={stat.featured ? 0.3 : 0.13}
                borderGlow={0.35}
                className={cn(
                  "dashboard-enter rounded-[22px] p-0 transition-transform duration-300 hover:-translate-y-1",
                  stat.featured ? "col-span-2 lg:col-span-4" : "lg:col-span-2",
                )}
                style={{
                  "--spotlight-card-surface": stat.featured ? "#211d1a" : "#fffdf9",
                  "--spotlight-card-shadow": stat.featured
                    ? "0 20px 45px -25px rgba(33, 29, 26, 0.65)"
                    : "0 12px 35px -24px rgba(67, 51, 38, 0.32)",
                  animationDelay: `${index * 70}ms`,
                } as React.CSSProperties}
              >
                <button
                  type="button"
                  onClick={stat.go}
                  className={cn(
                    "group flex h-full min-h-40 w-full flex-col p-4 text-left sm:min-h-44 sm:p-5",
                    stat.featured && "sm:p-6",
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className={cn("text-xs font-semibold sm:text-sm", stat.featured ? "text-white/65" : "text-muted")}>
                      {stat.label}
                    </span>
                    <span
                      className={cn(
                        "grid size-8 shrink-0 place-items-center rounded-xl transition-transform duration-300 group-hover:rotate-3 group-hover:scale-105",
                        stat.featured
                          ? "bg-white/10 text-[#f2b65b]"
                          : stat.hot
                            ? "bg-accent-wash text-accent-strong"
                            : "bg-paper text-ink-soft ring-1 ring-line/80",
                      )}
                    >
                      <Icon aria-hidden className="size-4" strokeWidth={1.8} />
                    </span>
                  </span>
                  <span
                    className={cn(
                      "mt-3 font-display text-[1.75rem] leading-none font-semibold tracking-[-0.04em] sm:text-4xl",
                      stat.featured && "sm:mt-4 sm:text-[2.65rem]",
                      !stat.featured && stat.hot && "text-accent-strong",
                    )}
                  >
                    {data ? (
                      stat.featured ? (
                        <ShinyText text={stat.value} color="#fffaf3" shineColor="#f2b65b" speed={4} delay={2} shineWidth={28} />
                      ) : (
                        stat.value
                      )
                    ) : (
                      "—"
                    )}
                  </span>
                  <span
                    className={cn(
                      "mt-auto flex items-center justify-between gap-2 pt-4 text-[11px] sm:text-xs",
                      stat.featured ? "text-white/50" : "text-muted",
                    )}
                  >
                    <span className="truncate">{stat.detail}</span>
                    <ArrowUpRight aria-hidden className="size-3.5 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </span>
                </button>
              </SpotlightCard>
            );
          })}
        </div>

        {error ? (
          <p role="alert" className="mt-5 rounded-2xl border border-accent/20 bg-accent-wash px-4 py-3 text-sm text-accent-strong">
            {error}
          </p>
        ) : null}

        <section className="mt-8" aria-label="Shop activity">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="tablist" aria-label="Dashboard sections" className="flex max-w-full gap-1 overflow-x-auto rounded-2xl border border-line/80 bg-card/75 p-1.5 shadow-sm backdrop-blur-sm">
              {tabs.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    type="button"
                    role="tab"
                    aria-selected={tab === item.key}
                    aria-controls={`panel-${item.key}`}
                    onClick={() => navigate({ tab: item.key })}
                    className={cn(
                      "inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-semibold whitespace-nowrap transition-all sm:px-4 sm:text-sm",
                      tab === item.key
                        ? "bg-night text-white shadow-md shadow-night/10"
                        : "text-muted hover:bg-paper hover:text-ink",
                    )}
                  >
                    <Icon aria-hidden className="size-4" strokeWidth={1.8} />
                    {item.label}
                    {item.count ? (
                      <span className="grid min-w-5 place-items-center rounded-full bg-accent-strong px-1.5 py-0.5 text-[10px] leading-none text-white" aria-label={`${item.count} need you`}>
                        {item.count}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            <span className="hidden items-center gap-2 text-xs text-muted sm:flex">
              <Sparkles aria-hidden className="size-3.5 text-mustard" />
              Updated automatically every 3 seconds
            </span>
          </div>

          <div className="mt-6 mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-xl font-semibold tracking-[-0.025em] sm:text-2xl">{panelCopy[0]}</h2>
              <p className="mt-1 text-xs leading-5 text-muted sm:text-sm">{panelCopy[1]}</p>
            </div>
            {tab === "chats" && active > 0 ? (
              <span className="hidden items-center gap-1.5 rounded-full bg-[#e3f1e8] px-3 py-1.5 text-xs font-medium text-[#1f6b43] md:inline-flex">
                <Bot aria-hidden className="size-3.5" /> {active} being handled
              </span>
            ) : null}
          </div>

          <div key={tab} id={`panel-${tab}`} role="tabpanel" className="dashboard-panel">
            {data === null ? (
              <div aria-hidden className="space-y-3 rounded-3xl border border-line bg-card/60 p-4">
                {[0, 1, 2, 3].map((i) => (
                  <span key={i} className="block h-16 animate-pulse rounded-2xl bg-paper-deep" />
                ))}
              </div>
            ) : tab === "chats" ? (
              <div className="overflow-hidden rounded-3xl border border-line/90 bg-card shadow-[0_20px_60px_-35px_rgba(61,44,31,0.35)] lg:grid lg:h-[calc(100dvh-27rem)] lg:min-h-[540px] lg:grid-cols-[350px_minmax(0,1fr)]">
                <div className={cn("min-h-0 overflow-y-auto lg:border-r lg:border-line", selected ? "hidden lg:block" : "block")}>
                  <div className="flex items-center justify-between border-b border-line bg-card px-4 py-3.5">
                    <span className="text-sm font-semibold">Inbox</span>
                    <span className="rounded-full bg-paper px-2.5 py-1 text-[11px] font-medium text-muted ring-1 ring-line">
                      {conversations.length} total
                    </span>
                  </div>
                  <ChatList conversations={conversations} selectedId={selected?.id ?? null} onSelect={(id) => navigate({ chat: id })} now={now} />
                </div>
                <div
                  className={cn(
                    "min-h-0",
                    selected ? "fixed inset-x-0 top-16 bottom-0 z-30 bg-card lg:static lg:z-auto lg:block" : "hidden lg:block",
                  )}
                >
                  {selected ? (
                    <ChatThread key={selected.id} conversation={selected} orders={orders} onBack={() => navigate({ chat: null })} onChanged={() => void refresh()} />
                  ) : (
                    <div className="grid h-full place-items-center bg-[radial-gradient(circle_at_center,rgba(226,167,46,0.08),transparent_55%)] px-6 text-center">
                      <div className="max-w-xs">
                        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-paper text-accent-strong shadow-sm ring-1 ring-line">
                          <MessagesSquare aria-hidden className="size-6" strokeWidth={1.5} />
                        </span>
                        <h3 className="mt-4 font-display text-lg font-semibold">Pick up a conversation</h3>
                        <p className="mt-2 text-sm leading-6 text-muted">Choose a chat to read the negotiation, reply as Ada, or hand control back to Sowo.</p>
                        <Link href="/try" className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-accent-strong underline-offset-4 hover:underline">
                          Try the buyer simulator <ArrowUpRight aria-hidden className="size-3.5" />
                        </Link>
                      </div>
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
        </section>
      </div>
    </div>
  );
}
