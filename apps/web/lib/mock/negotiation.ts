// Server-side pricing rules for the mock. These decide prices; the scripted
// "model" in agent.ts only reads the results.

import type { EvaluateOfferCall, Kobo, Product } from "@sowo/shared";

/** Share of the base-to-floor gap conceded on the 1st, 2nd and 3rd counter. */
const CONCESSION_STEPS = [0.4, 0.7, 1] as const;
const ROUND_TO_KOBO = 50_000; // ₦500

export interface OfferHistory {
  countersMade: number;
  lastCounterKobo?: Kobo;
}

export const NO_OFFERS_YET: OfferHistory = { countersMade: 0 };

export function evaluateOffer(
  product: Pick<Product, "basePriceKobo" | "floorPriceKobo">,
  offerKobo: Kobo,
  history: OfferHistory,
): { output: EvaluateOfferCall["output"]; history: OfferHistory } {
  const { basePriceKobo: base, floorPriceKobo: floor } = product;

  if (offerKobo >= floor) {
    return {
      output: { decision: "ACCEPT", agreedPriceKobo: Math.min(offerKobo, base) },
      history,
    };
  }

  const step =
    CONCESSION_STEPS[Math.min(history.countersMade, CONCESSION_STEPS.length - 1)] ?? 1;
  const rounded = Math.round((base - (base - floor) * step) / ROUND_TO_KOBO) * ROUND_TO_KOBO;
  const ceiling = history.lastCounterKobo ?? base;
  const counterKobo = Math.min(Math.max(rounded, floor), ceiling);

  return {
    output: { decision: counterKobo <= floor ? "HOLD" : "COUNTER", counterKobo },
    history: { countersMade: history.countersMade + 1, lastCounterKobo: counterKobo },
  };
}

/** Delivery fees in kobo. The real list will come from vendor settings. */
export const DELIVERY_FEES: Record<string, Kobo> = {
  Ikeja: 250_000,
  Maryland: 250_000,
  Gbagada: 250_000,
  Yaba: 200_000,
  Surulere: 200_000,
  Festac: 300_000,
  Lekki: 350_000,
  "Victoria Island": 350_000,
  Ajah: 400_000,
  Ikorodu: 400_000,
  Ibadan: 500_000,
  "Ile-Ife": 500_000,
  Abuja: 600_000,
};

export function findDeliveryArea(text: string): string | undefined {
  const lower = text.toLowerCase();
  return Object.keys(DELIVERY_FEES).find((area) => {
    const names = area === "Victoria Island" ? ["victoria island", "v.i", "vi"] : [area.toLowerCase()];
    return names.some((name) => new RegExp(`(^|[^a-z])${escapeRegExp(name)}([^a-z]|$)`).test(lower));
  });
}

/**
 * Pull a naira amount out of a buyer's message, in kobo.
 * Understands "35k", "₦41,000", "41000", "40 thousand", and the haggling
 * shorthand "make it 41", where a bare number under 1,000 means thousands.
 * Shoe sizes ("size 43") are ignored.
 */
export function parseOfferKobo(text: string): Kobo | undefined {
  const cleaned = text.toLowerCase().replace(/size\s*\d+/g, " ");
  const match = cleaned.match(/(?:₦|ngn|n)?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k\b|thousand)?/);
  if (!match?.[1]) return undefined;

  const amount = Number(match[1].replace(/,/g, ""));
  if (!Number.isFinite(amount) || amount <= 0) return undefined;

  const naira = match[2] || amount < 1000 ? amount * 1000 : amount;
  return Math.round(naira * 100);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
