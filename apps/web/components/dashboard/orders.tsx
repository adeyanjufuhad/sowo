import { formatNaira, type Order } from "@sowo/shared";
import { Receipt } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FulfillmentBadge, PaymentBadge } from "./badges";
import { MarkPaid, awaitsTransfer } from "./mark-paid";

const orderNo = (order: Order) => order.id.replace("ord_", "#");
const needsPacking = (order: Order) => order.paymentStatus === "PAID" && order.fulfillmentStatus === "PACKAGING";

export function OrdersView({ orders, now }: { orders: Order[]; now: number }) {
  if (orders.length === 0) {
    return (
      <div className="rounded-3xl border border-line bg-card px-6 py-20 text-center text-sm text-muted shadow-sm">
        <span className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-paper text-accent-strong ring-1 ring-line">
          <Receipt aria-hidden className="size-6" strokeWidth={1.5} />
        </span>
        <p className="font-display text-lg font-semibold text-ink">No orders yet</p>
        <p className="mt-2">They&apos;ll appear here when Sowo sends a payment link.</p>
      </div>
    );
  }

  return (
    <>
      {/* Phones: cards */}
      <ul className="space-y-3 md:hidden">
        {orders.map((o) => (
          <li key={o.id} className={cn("rounded-3xl border border-line bg-card p-4 shadow-sm", needsPacking(o) && "border-accent/40 bg-accent-wash/25 ring-1 ring-accent/20")}>
            <div className="flex items-baseline justify-between gap-3">
              <p className="font-semibold">
                {orderNo(o)} · {o.customerName}
              </p>
              <p className="font-mono text-sm">{formatNaira(o.totalKobo)}</p>
            </div>
            <p className="mt-1 text-sm text-muted">
              {o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}
              {o.deliveryArea ? ` · to ${o.deliveryArea}` : ""}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <PaymentBadge status={o.paymentStatus} />
              {o.paymentStatus === "PAID" ? <FulfillmentBadge status={o.fulfillmentStatus} /> : null}
              <span className="ml-auto text-xs text-muted">{relativeTime(o.createdAt, now)}</span>
            </div>
            {awaitsTransfer(o) ? <MarkPaid order={o} now={now} className="mt-3 border-t border-line pt-3" /> : null}
          </li>
        ))}
      </ul>

      {/* Larger screens: table */}
      <div className="hidden overflow-x-auto rounded-3xl border border-line/90 bg-card shadow-[0_20px_60px_-40px_rgba(61,44,31,0.35)] md:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Orders, newest first</caption>
          <thead className="border-b border-line bg-paper/60 text-[11px] tracking-[0.08em] text-muted uppercase">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Order</th>
              <th scope="col" className="px-4 py-3 font-medium">Customer</th>
              <th scope="col" className="px-4 py-3 font-medium">Items</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Delivery</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Total</th>
              <th scope="col" className="px-4 py-3 font-medium">Payment</th>
              <th scope="col" className="px-4 py-3 font-medium">Fulfilment</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Placed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {orders.map((o) => (
              <tr key={o.id} className={cn("transition-colors hover:bg-paper/55", needsPacking(o) && "bg-accent-wash/35 hover:bg-accent-wash/50")}>
                <td className="px-4 py-3 font-mono">{orderNo(o)}</td>
                <td className="px-4 py-3 font-medium whitespace-nowrap">{o.customerName}</td>
                <td className="px-4 py-3 text-ink-soft">
                  {o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}
                  {o.deliveryArea ? <span className="block text-xs text-muted">to {o.deliveryArea}</span> : null}
                </td>
                <td className="px-4 py-3 text-right font-mono whitespace-nowrap text-ink-soft">{formatNaira(o.deliveryFeeKobo)}</td>
                <td className="px-4 py-3 text-right font-mono font-medium whitespace-nowrap">{formatNaira(o.totalKobo)}</td>
                <td className="px-4 py-3">
                  <PaymentBadge status={o.paymentStatus} />
                  {awaitsTransfer(o) ? <MarkPaid order={o} now={now} className="mt-2 min-w-48" /> : null}
                </td>
                <td className="px-4 py-3">
                  {o.paymentStatus === "PAID" ? <FulfillmentBadge status={o.fulfillmentStatus} /> : <span className="text-muted">·</span>}
                </td>
                <td className="px-4 py-3 text-right text-muted whitespace-nowrap">{relativeTime(o.createdAt, now)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
