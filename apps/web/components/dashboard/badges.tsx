import type { ConversationStatus, FulfillmentStatus, PaymentStatus } from "@sowo/shared";
import { cn } from "@/lib/utils";

const base = "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap";

const CONVERSATION: Record<ConversationStatus, { label: string; className: string; dot?: string }> = {
  NEEDS_ATTENTION: { label: "Needs you", className: "bg-accent-strong text-white", dot: "bg-white" },
  AI_ACTIVE: { label: "Sowo active", className: "bg-card text-ink-soft ring-1 ring-line", dot: "bg-[#2f8f5b]" },
  HUMAN_TAKEOVER: { label: "You're replying", className: "bg-indigo/10 text-indigo ring-1 ring-indigo/20" },
  CLOSED: { label: "Closed", className: "bg-paper-deep text-muted" },
};

export function ConversationBadge({ status }: { status: ConversationStatus }) {
  const s = CONVERSATION[status];
  return (
    <span className={cn(base, s.className)}>
      {s.dot ? <span aria-hidden className={cn("size-1.5 rounded-full", s.dot)} /> : null}
      {s.label}
    </span>
  );
}

const PAYMENT: Record<PaymentStatus, { label: string; className: string }> = {
  PAID: { label: "Paid", className: "bg-[#e3f1e8] text-[#1f6b43]" },
  PENDING: { label: "Awaiting payment", className: "bg-mustard/20 text-[#7a5a12]" },
  FAILED: { label: "Failed", className: "bg-accent-wash text-accent-strong" },
  REFUNDED: { label: "Refunded", className: "bg-paper-deep text-muted" },
};

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  const s = PAYMENT[status];
  return <span className={cn(base, s.className)}>{s.label}</span>;
}

const FULFILMENT: Record<FulfillmentStatus, { label: string; className: string }> = {
  UNFULFILLED: { label: "Not started", className: "bg-paper-deep text-muted" },
  PACKAGING: { label: "Pack now", className: "bg-accent-strong text-white" },
  SHIPPED: { label: "Shipped", className: "bg-indigo/10 text-indigo" },
  DELIVERED: { label: "Delivered", className: "bg-[#e3f1e8] text-[#1f6b43]" },
};

export function FulfillmentBadge({ status }: { status: FulfillmentStatus }) {
  const s = FULFILMENT[status];
  return <span className={cn(base, s.className)}>{s.label}</span>;
}
