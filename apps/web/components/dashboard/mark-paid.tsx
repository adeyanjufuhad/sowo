"use client";

import { formatNaira, type Order } from "@sowo/shared";
import { BadgeCheck, Landmark } from "lucide-react";
import { useState } from "react";
import { api, ApiRequestError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** A bank-transfer order is only paid once Ada has seen the money in her own account. */
export const awaitsTransfer = (order: Order) => order.paymentMethod === "MANUAL" && order.paymentStatus === "PENDING";

/**
 * Ada's "Mark paid" control for a bank-transfer order. Two taps on purpose: the first asks her to
 * check her bank app, the second confirms. The order list picks up the new status on its next refresh.
 */
export function MarkPaid({
  order,
  now,
  onPaid,
  className,
}: {
  order: Order;
  /** For "sent a receipt 5m ago". Defaults to when this control appeared. */
  now?: number;
  onPaid?: () => void;
  className?: string;
}) {
  const [mountedAt] = useState(() => Date.now());
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (done) {
    return (
      <p role="status" className={cn("flex items-center gap-1.5 text-sm font-medium text-[#1f6b43]", className)}>
        <BadgeCheck aria-hidden className="size-4" strokeWidth={1.75} /> Marked paid. The buyer has their receipt.
      </p>
    );
  }
  if (!awaitsTransfer(order)) return null;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.markOrderPaid(order.id);
      setDone(true);
      onPaid?.();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't mark it paid. Try again.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="flex items-center gap-1.5 text-xs text-muted">
        <Landmark aria-hidden className="size-3.5" strokeWidth={1.75} />
        {order.receiptReportedAt
          ? `Buyer sent a receipt ${relativeTime(order.receiptReportedAt, now ?? mountedAt)}. Check your bank app.`
          : "Waiting for the buyer's transfer."}
      </p>
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm">
            Is <span className="font-mono font-medium">{formatNaira(order.totalKobo)}</span> in your account?
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={confirm}
            className="h-8 rounded-full bg-accent-strong px-3.5 text-sm font-medium text-white transition-[transform,background-color] hover:bg-[#a33515] active:scale-[0.98] disabled:opacity-60"
          >
            {busy ? "Marking…" : "Yes, mark paid"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming(false)}
            className="h-8 rounded-full px-3 text-sm text-ink-soft ring-1 ring-line transition-colors hover:bg-paper-deep disabled:opacity-60"
          >
            Not yet
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="h-8 rounded-full bg-ink px-3.5 text-sm font-medium text-paper transition-[transform,opacity] hover:opacity-90 active:scale-[0.98]"
        >
          Mark paid
        </button>
      )}
      {error ? (
        <p role="alert" className="text-sm text-accent-strong">
          {error}
        </p>
      ) : null}
    </div>
  );
}
