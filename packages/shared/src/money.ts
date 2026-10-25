import type { Kobo } from "./api";

const KOBO_PER_NAIRA = 100;

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Format integer kobo as naira for display: 4350000 -> "₦43,500".
 * Kobo are shown only when non-zero: 4350050 -> "₦43,500.50".
 * Hand-rolled rather than Intl so server and browser render identical text.
 */
export function formatNaira(kobo: Kobo): string {
  if (!Number.isSafeInteger(kobo)) {
    throw new TypeError(`formatNaira expects integer kobo, got ${kobo}`);
  }
  const sign = kobo < 0 ? "-" : "";
  const abs = Math.abs(kobo);
  const naira = Math.floor(abs / KOBO_PER_NAIRA);
  const remainder = abs % KOBO_PER_NAIRA;
  const fraction = remainder === 0 ? "" : `.${String(remainder).padStart(2, "0")}`;
  return `${sign}₦${groupThousands(String(naira))}${fraction}`;
}

/** Convert whole or fractional naira to integer kobo: 435.5 -> 43550. */
export function nairaToKobo(naira: number): Kobo {
  if (!Number.isFinite(naira)) {
    throw new TypeError(`nairaToKobo expects a finite number, got ${naira}`);
  }
  return Math.round(naira * KOBO_PER_NAIRA);
}
