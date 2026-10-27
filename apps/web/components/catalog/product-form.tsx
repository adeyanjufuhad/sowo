"use client";

import { nairaToKobo, type Product, type ProductCreate } from "@sowo/shared";
import { useId, useState, type FormEvent } from "react";
import { ApiRequestError } from "@/lib/api";

const field =
  "h-10 w-full rounded-xl bg-paper px-3 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong";

/** "35,000" or "₦35000.50" -> kobo, or null if it isn't a positive amount. */
export function parseNaira(text: string): number | null {
  const cleaned = text.replace(/[₦,\s]/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const kobo = nairaToKobo(Number(cleaned));
  return kobo > 0 ? kobo : null;
}

const naira = (kobo: number) => String(kobo / 100);

/** Add a product, or change one. The "lowest price" is the floor: only the vendor ever sees it. */
export function ProductForm({
  product,
  onSave,
  onCancel,
}: {
  product?: Product;
  onSave: (input: ProductCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const id = useId();
  const [sku, setSku] = useState(product?.sku ?? "");
  const [name, setName] = useState(product?.name ?? "");
  const [price, setPrice] = useState(product ? naira(product.basePriceKobo) : "");
  const [floor, setFloor] = useState(product ? naira(product.floorPriceKobo) : "");
  const [stock, setStock] = useState(String(product?.stockOnHand ?? 1));
  const [size, setSize] = useState(product?.size ?? "");
  const [colour, setColour] = useState(product?.colour ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [imageUrl, setImageUrl] = useState(product?.imageUrl ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const basePriceKobo = parseNaira(price);
    const floorPriceKobo = parseNaira(floor);
    const stockOnHand = Number(stock);
    if (basePriceKobo === null) return setError("Enter the price in naira, like 45000.");
    if (floorPriceKobo === null) return setError("Enter your lowest price in naira, like 40000.");
    if (floorPriceKobo > basePriceKobo) return setError("Your lowest price can't be higher than the price.");
    if (!Number.isInteger(stockOnHand) || stockOnHand < 0) return setError("Stock must be a whole number, 0 or more.");
    setBusy(true);
    setError(null);
    try {
      await onSave({
        sku,
        name,
        description,
        size: size || null,
        colour: colour || null,
        basePriceKobo,
        floorPriceKobo,
        stockOnHand,
        imageUrl,
      });
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't save. Check your connection and try again.");
      setBusy(false);
    }
  }

  const label = "mb-1 block text-xs font-medium text-ink-soft";
  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl bg-paper-deep/60 p-4 ring-1 ring-line">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label htmlFor={`${id}-name`} className={label}>Name</label>
          <input id={`${id}-name`} value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-sku`} className={label}>Code (sku)</label>
          <input id={`${id}-sku`} value={sku} onChange={(e) => setSku(e.target.value)} required maxLength={64} placeholder="LOAF-BLK-43" className={`${field} font-mono`} />
        </div>
        <div>
          <label htmlFor={`${id}-stock`} className={label}>In stock</label>
          <input id={`${id}-stock`} value={stock} onChange={(e) => setStock(e.target.value)} inputMode="numeric" required className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-price`} className={label}>Price (₦)</label>
          <input id={`${id}-price`} value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" required placeholder="45000" className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-floor`} className={label}>Lowest you&apos;ll accept (₦)</label>
          <input id={`${id}-floor`} value={floor} onChange={(e) => setFloor(e.target.value)} inputMode="decimal" required placeholder="40000" className={field} />
          <p className="mt-1 text-xs text-muted">Only you see this. Sowo never tells buyers.</p>
        </div>
        <div>
          <label htmlFor={`${id}-size`} className={label}>Size</label>
          <input id={`${id}-size`} value={size} onChange={(e) => setSize(e.target.value)} maxLength={32} className={field} />
        </div>
        <div>
          <label htmlFor={`${id}-colour`} className={label}>Colour</label>
          <input id={`${id}-colour`} value={colour} onChange={(e) => setColour(e.target.value)} maxLength={64} className={field} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor={`${id}-description`} className={label}>Description</label>
          <textarea id={`${id}-description`} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={2} className={`${field} h-auto py-2`} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor={`${id}-image`} className={label}>Picture address (optional)</label>
          <input id={`${id}-image`} value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} inputMode="url" placeholder="https://…" maxLength={500} className={field} />
        </div>
      </div>
      {error ? (
        <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
          {error}
        </p>
      ) : null}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="h-10 rounded-full bg-accent-strong px-5 text-sm font-medium text-white hover:bg-[#a33515] disabled:opacity-60">
          {busy ? "Saving…" : product ? "Save changes" : "Add product"}
        </button>
        <button type="button" onClick={onCancel} className="h-10 rounded-full px-4 text-sm font-medium text-ink-soft hover:bg-paper-deep hover:text-ink">
          Cancel
        </button>
      </div>
    </form>
  );
}
