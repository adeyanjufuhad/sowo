"use client";

import { formatNaira, type DeliveryZone } from "@sowo/shared";
import { useId, useState, type FormEvent } from "react";
import { api, ApiRequestError } from "@/lib/api";
import { parseNaira } from "./product-form";

const field =
  "h-10 w-full rounded-xl bg-paper px-3 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong";

/** A fee of ₦0 is valid (free delivery), so this accepts zero where parseNaira does not. */
function parseFee(text: string): number | null {
  if (/^[₦,\s]*0+(\.0{1,2})?\s*$/.test(text)) return 0;
  return parseNaira(text);
}

function ZoneRow({ zone, onChange }: { zone: DeliveryZone; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [area, setArea] = useState(zone.area);
  const [fee, setFee] = useState(String(zone.feeKobo / 100));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setEditing(false);
      onChange();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    const feeKobo = parseFee(fee);
    if (feeKobo === null) return setError("Enter the fee in naira, like 2500, or 0 for free delivery.");
    void run(() => api.updateDeliveryZone(zone.id, { area, feeKobo }));
  }

  if (editing) {
    return (
      <li className="py-3">
        <form onSubmit={save} className="flex flex-wrap items-end gap-2">
          <label className="min-w-40 flex-1 text-xs font-medium text-ink-soft">
            Area
            <input value={area} onChange={(e) => setArea(e.target.value)} required maxLength={100} className={`${field} mt-1`} />
          </label>
          <label className="w-32 text-xs font-medium text-ink-soft">
            Fee (₦)
            <input value={fee} onChange={(e) => setFee(e.target.value)} inputMode="decimal" required className={`${field} mt-1`} />
          </label>
          <button type="submit" disabled={busy} className="h-10 rounded-full bg-accent-strong px-4 text-sm font-medium text-white disabled:opacity-60">
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)} className="h-10 rounded-full px-3 text-sm text-ink-soft hover:bg-paper-deep">
            Cancel
          </button>
        </form>
        {error ? <p role="alert" className="mt-2 text-sm text-accent-strong">{error}</p> : null}
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-3">
      <span className="font-medium">{zone.area}</span>
      <span className="flex items-center gap-1">
        <span className="mr-2 font-mono text-sm text-ink-soft">{zone.feeKobo === 0 ? "Free" : formatNaira(zone.feeKobo)}</span>
        <button type="button" onClick={() => setEditing(true)} className="rounded-full px-3 py-1.5 text-sm text-ink-soft hover:bg-paper-deep hover:text-ink">
          Edit
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (window.confirm(`Stop delivering to ${zone.area}?`)) void run(() => api.deleteDeliveryZone(zone.id));
          }}
          className="rounded-full px-3 py-1.5 text-sm text-accent-strong hover:bg-accent-wash disabled:opacity-60"
        >
          Remove
        </button>
      </span>
      {error ? <p role="alert" className="w-full text-sm text-accent-strong">{error}</p> : null}
    </li>
  );
}

/** The areas a vendor delivers to and what each costs. Buyers only get quotes for areas on this list. */
export function ZonesEditor({ zones, onChange }: { zones: DeliveryZone[]; onChange: () => void }) {
  const id = useId();
  const [area, setArea] = useState("");
  const [fee, setFee] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    const feeKobo = parseFee(fee);
    if (feeKobo === null) return setError("Enter the fee in naira, like 2500, or 0 for free delivery.");
    setBusy(true);
    setError(null);
    try {
      await api.createDeliveryZone({ area, feeKobo });
      setArea("");
      setFee("");
      onChange();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't add that area. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby={`${id}-title`} className="rounded-3xl bg-card p-5 ring-1 ring-line sm:p-6">
      <h2 id={`${id}-title`} className="text-base font-semibold">Where you deliver</h2>
      <p className="mt-1 text-sm text-muted">Sowo only quotes delivery to these areas, at these fees.</p>
      {zones.length === 0 ? (
        <p className="mt-4 rounded-xl bg-paper-deep px-3.5 py-3 text-sm text-ink-soft">
          No delivery areas yet, so Sowo can&apos;t price an order. Add your first below.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {zones.map((zone) => (
            <ZoneRow key={zone.id} zone={zone} onChange={onChange} />
          ))}
        </ul>
      )}
      <form onSubmit={add} className="mt-4 flex flex-wrap items-end gap-2 border-t border-line pt-4">
        <label htmlFor={`${id}-area`} className="min-w-40 flex-1 text-xs font-medium text-ink-soft">
          New area
          <input id={`${id}-area`} value={area} onChange={(e) => setArea(e.target.value)} required maxLength={100} placeholder="Ikeja" className={`${field} mt-1`} />
        </label>
        <label htmlFor={`${id}-fee`} className="w-32 text-xs font-medium text-ink-soft">
          Fee (₦)
          <input id={`${id}-fee`} value={fee} onChange={(e) => setFee(e.target.value)} inputMode="decimal" required placeholder="2500" className={`${field} mt-1`} />
        </label>
        <button type="submit" disabled={busy} className="h-10 rounded-full bg-accent-strong px-5 text-sm font-medium text-white hover:bg-[#a33515] disabled:opacity-60">
          Add area
        </button>
      </form>
      {error ? <p role="alert" className="mt-2 text-sm text-accent-strong">{error}</p> : null}
    </section>
  );
}
