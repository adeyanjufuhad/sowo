import { describe, expect, it } from "vitest";
import { formatNaira, nairaToKobo } from "./money";

describe("formatNaira", () => {
  it("formats the loafers total", () => {
    expect(formatNaira(4_350_000)).toBe("₦43,500");
  });

  it("groups thousands and millions", () => {
    expect(formatNaira(0)).toBe("₦0");
    expect(formatNaira(50_000)).toBe("₦500");
    expect(formatNaira(100_000)).toBe("₦1,000");
    expect(formatNaira(123_456_700)).toBe("₦1,234,567");
  });

  it("shows kobo only when they are not zero", () => {
    expect(formatNaira(4_350_050)).toBe("₦43,500.50");
    expect(formatNaira(105)).toBe("₦1.05");
  });

  it("puts the sign before the naira symbol", () => {
    expect(formatNaira(-250_000)).toBe("-₦2,500");
  });

  it("rejects non-integer kobo", () => {
    expect(() => formatNaira(43_500.5)).toThrow(TypeError);
    expect(() => formatNaira(Number.NaN)).toThrow(TypeError);
  });
});

describe("nairaToKobo", () => {
  it("converts naira to integer kobo", () => {
    expect(nairaToKobo(43_500)).toBe(4_350_000);
    expect(nairaToKobo(0.1 + 0.2)).toBe(30);
  });
});
