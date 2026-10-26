/* eslint-disable @next/next/no-img-element -- small local SVG placeholders, no optimisation needed */
import { formatNaira, type Product } from "@sowo/shared";
import { EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

function Stock({ count }: { count: number }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap",
        count === 0 ? "bg-accent-wash text-accent-strong" : count <= 2 ? "bg-mustard/20 text-[#7a5a12]" : "bg-paper-deep text-ink-soft",
      )}
    >
      {count === 0 ? "Sold out" : count <= 2 ? `${count} left` : `${count} in stock`}
    </span>
  );
}

export function ProductsView({ products }: { products: Product[] }) {
  return (
    <div className="space-y-3">
      <p className="flex items-start gap-2 rounded-2xl bg-card px-4 py-3 text-sm text-ink-soft ring-1 ring-line">
        <EyeOff aria-hidden className="mt-0.5 size-4 shrink-0 text-accent-strong" strokeWidth={1.75} />
        Floor prices are visible to you only. Sowo&apos;s server uses them to haggle, but they never reach buyers or the
        model.
      </p>

      {/* Phones: cards */}
      <ul className="grid gap-3 sm:grid-cols-2 md:hidden">
        {products.map((p) => (
          <li key={p.id} className="flex gap-3 rounded-2xl bg-card p-3 ring-1 ring-line">
            <img src={p.imageUrl} alt="" width={64} height={64} className="size-16 shrink-0 rounded-xl" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{p.name}</p>
              <p className="font-mono text-xs text-muted">{p.sku}</p>
              <dl className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <div className="flex gap-1">
                  <dt className="text-muted">Price</dt>
                  <dd className="font-mono">{formatNaira(p.basePriceKobo)}</dd>
                </div>
                <div className="flex gap-1">
                  <dt className="text-muted">Floor</dt>
                  <dd className="font-mono text-accent-strong">{formatNaira(p.floorPriceKobo)}</dd>
                </div>
                <dd>
                  <Stock count={p.stockOnHand} />
                </dd>
              </dl>
            </div>
          </li>
        ))}
      </ul>

      {/* Larger screens: table */}
      <div className="hidden overflow-x-auto rounded-2xl bg-card ring-1 ring-line md:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Products with price, floor price and stock</caption>
          <thead className="border-b border-line text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Product</th>
              <th scope="col" className="px-4 py-3 font-medium">SKU</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Price</th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                <span className="inline-flex items-center gap-1">
                  <EyeOff aria-hidden className="size-3.5" strokeWidth={1.75} /> Floor (only you)
                </span>
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">Stock</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {products.map((p) => (
              <tr key={p.id}>
                <td className="px-4 py-2.5">
                  <span className="flex items-center gap-3">
                    <img src={p.imageUrl} alt="" width={40} height={40} className="size-10 rounded-lg" />
                    <span className="font-medium">{p.name}</span>
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted">{p.sku}</td>
                <td className="px-4 py-2.5 text-right font-mono">{formatNaira(p.basePriceKobo)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-accent-strong">{formatNaira(p.floorPriceKobo)}</td>
                <td className="px-4 py-2.5 text-right">
                  <Stock count={p.stockOnHand} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
