"use client";

/* eslint-disable @next/next/no-img-element -- the vendor's own small, already-shrunk pictures */
import { formatNaira, type DeliveryZone, type Product } from "@sowo/shared";
import { ImageOff } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiRequestError, USING_MOCK } from "@/lib/api";
import { productImageSrc } from "@/lib/product-image";
import { ProductForm } from "./product-form";
import { ZonesEditor } from "./zones-editor";

/** Each category once, whatever the capitals, in the spelling the vendor used first. */
function categoriesOf(products: Product[]): string[] {
  const seen = new Map<string, string>();
  for (const p of products) {
    const name = p.category?.trim();
    if (name && !seen.has(name.toLowerCase())) seen.set(name.toLowerCase(), name);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b));
}

function ProductRow({ product, categories, onChange }: { product: Product; categories: string[]; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (editing) {
    return (
      <li className="py-3">
        <ProductForm
          product={product}
          categories={categories}
          onCancel={() => setEditing(false)}
          onSave={async (input) => {
            await api.updateProduct(product.id, input);
            setEditing(false);
            onChange();
          }}
        />
      </li>
    );
  }

  async function remove() {
    if (!window.confirm(`Remove ${product.name}? Orders already placed for it are kept.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteProduct(product.id);
      onChange();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't remove it. Try again.");
      setBusy(false);
    }
  }

  const picture = productImageSrc(product.imageUrl);
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          {picture ? (
            <img src={picture} alt="" width={44} height={44} className="size-11 shrink-0 rounded-lg object-cover ring-1 ring-line" />
          ) : (
            <span aria-hidden className="grid size-11 shrink-0 place-items-center rounded-lg bg-paper text-muted ring-1 ring-line">
              <ImageOff className="size-4" strokeWidth={1.5} />
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate font-medium">{product.name}</p>
            <p className="truncate text-xs text-muted">
              <span className="font-mono">{product.sku}</span>
              {product.category ? <> · {product.category}</> : null}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm whitespace-nowrap">
          <span className="font-mono">{formatNaira(product.basePriceKobo)}</span>
          <span className="text-xs text-muted" title="The lowest price you'll accept. Only you see it.">
            lowest {formatNaira(product.floorPriceKobo)}
          </span>
          <span className={product.stockOnHand === 0 ? "font-medium text-accent-strong" : "text-ink-soft"}>
            {product.stockOnHand === 0 ? "Sold out" : `${product.stockOnHand} in stock`}
          </span>
          <span className="-ml-3 flex items-center sm:ml-0">
            <button type="button" onClick={() => setEditing(true)} className="rounded-full px-3 py-1.5 text-ink-soft hover:bg-paper-deep hover:text-ink">
              Edit
            </button>
            <button type="button" onClick={remove} disabled={busy} className="rounded-full px-3 py-1.5 text-accent-strong hover:bg-accent-wash disabled:opacity-60">
              Remove
            </button>
          </span>
        </div>
      </div>
      {error ? <p role="alert" className="mt-2 text-sm text-accent-strong">{error}</p> : null}
    </li>
  );
}

/** A vendor's products and delivery areas. What Sowo sells and quotes comes only from here. */
export function CatalogManager() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [zones, setZones] = useState<DeliveryZone[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.listProducts(), api.listDeliveryZones()])
      .then(([p, z]) => {
        setProducts(p.products);
        setZones(z.zones);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiRequestError ? err.message : "Couldn't load your catalog."));
  }, []);

  useEffect(() => {
    if (!USING_MOCK) load();
  }, [load]);

  if (USING_MOCK) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <p role="status" className="rounded-xl bg-paper-deep px-3.5 py-3 text-sm text-ink-soft">
          Managing your catalog needs the real backend, and this copy of Sowo runs in demo mode.{" "}
          <Link href="/dashboard" className="font-medium text-accent-strong underline-offset-4 hover:underline">
            Back to the demo dashboard
          </Link>
          .
        </p>
      </div>
    );
  }

  if (!products || !zones) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        {error ? (
          <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">{error}</p>
        ) : (
          <div className="h-96 animate-pulse rounded-3xl bg-paper-deep" aria-hidden />
        )}
      </div>
    );
  }

  const categories = categoriesOf(products);
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 py-8 sm:px-6">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-[-0.03em]">Your catalog</h1>
        <p className="mt-1.5 text-sm text-muted">
          Sowo sells what&apos;s here, at these prices, and delivers where you say. Changes apply to the very next message.
        </p>
      </div>
      {error ? (
        <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">{error}</p>
      ) : null}

      <section aria-labelledby="products-title" className="rounded-3xl bg-card p-5 ring-1 ring-line sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 id="products-title" className="text-base font-semibold">Products</h2>
          {adding ? null : (
            <button type="button" onClick={() => setAdding(true)} className="h-9 rounded-full bg-accent-strong px-4 text-sm font-medium text-white hover:bg-[#a33515]">
              Add product
            </button>
          )}
        </div>
        {adding ? (
          <div className="mt-4">
            <ProductForm
              categories={categories}
              onCancel={() => setAdding(false)}
              onSave={async (input) => {
                await api.createProduct(input);
                setAdding(false);
                load();
              }}
            />
          </div>
        ) : null}
        {products.length === 0 && !adding ? (
          <p className="mt-4 rounded-xl bg-paper-deep px-3.5 py-3 text-sm text-ink-soft">
            No products yet. Add what you sell and Sowo can start talking about it.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {products.map((product) => (
              <ProductRow key={product.id} product={product} categories={categories} onChange={load} />
            ))}
          </ul>
        )}
      </section>

      <ZonesEditor zones={zones} onChange={load} />
    </div>
  );
}
