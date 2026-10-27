import { afterEach, describe, expect, it, vi } from "vitest";
import { safeNext } from "./safe-next";
import { backendUrl, isProxiedPath, isSameOrigin, sessionCookieOptions } from "./session-proxy";

afterEach(() => vi.unstubAllEnvs());

describe("isProxiedPath", () => {
  it("lets the dashboard, auth and simulator calls through", () => {
    for (const path of [["auth", "login"], ["conversations", "c1", "messages"], ["orders"], ["products"], ["simulator", "messages"], ["vendor", "settings"], ["delivery-zones", "z1"]]) {
      expect(isProxiedPath(path)).toBe(true);
    }
  });

  it("keeps webhooks, health checks and anything else out", () => {
    for (const path of [["webhooks", "whatsapp"], ["health"], ["docs"], ["openapi.json"], []]) {
      expect(isProxiedPath(path)).toBe(false);
    }
  });

  it("refuses attempts to climb out of the allowed prefixes", () => {
    expect(isProxiedPath(["orders", "..", "webhooks", "whatsapp"])).toBe(false);
    expect(isProxiedPath(["orders", "", "x"])).toBe(false);
    expect(isProxiedPath(["orders", "..\\x"])).toBe(false);
  });
});

describe("isSameOrigin", () => {
  it("accepts requests from this site", () => {
    expect(isSameOrigin("https://sowo.example", "sowo.example")).toBe(true);
    expect(isSameOrigin("http://localhost:3000", "localhost:3000")).toBe(true);
  });

  it("refuses another site, and garbage", () => {
    expect(isSameOrigin("https://evil.example", "sowo.example")).toBe(false);
    expect(isSameOrigin("https://sowo.example.evil.example", "sowo.example")).toBe(false);
    expect(isSameOrigin("not a url", "sowo.example")).toBe(false);
  });

  it("allows requests that carry no Origin, which browsers don't send cross-site", () => {
    expect(isSameOrigin(null, "sowo.example")).toBe(true);
  });
});

describe("safeNext", () => {
  it("keeps paths on this site", () => {
    expect(safeNext("/dashboard?tab=orders")).toBe("/dashboard?tab=orders");
    expect(safeNext("/try")).toBe("/try");
  });

  it("falls back for anything that could leave the site or loop", () => {
    for (const value of ["https://evil.example", "//evil.example", "/\\evil.example", "dashboard", "", null, undefined, "/login", "/signup?x=1"]) {
      expect(safeNext(value)).toBe("/dashboard");
    }
  });
});

describe("backendUrl", () => {
  it("prefers the server-side address and drops trailing slashes", () => {
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000/");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    expect(backendUrl()).toBe("http://api:8000");
  });

  it("falls back to the public address, and to nothing", () => {
    vi.stubEnv("API_INTERNAL_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    expect(backendUrl()).toBe("http://localhost:8000");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(backendUrl()).toBeNull();
  });
});

describe("sessionCookieOptions", () => {
  it("is httpOnly, lax and lasts until the session expires, at most 30 days", () => {
    const inTwoDays = new Date(Date.now() + 2 * 86_400_000).toISOString();
    const options = sessionCookieOptions(inTwoDays);
    expect(options.httpOnly).toBe(true);
    expect(options.sameSite).toBe("lax");
    expect(options.path).toBe("/");
    expect(options.maxAge).toBeGreaterThan(2 * 86_400 - 60);
    expect(options.maxAge).toBeLessThanOrEqual(2 * 86_400);

    const farAway = new Date(Date.now() + 400 * 86_400_000).toISOString();
    expect(sessionCookieOptions(farAway).maxAge).toBe(30 * 86_400);
  });

  it("does not outlive a missing or past expiry", () => {
    expect(sessionCookieOptions(undefined).maxAge).toBe(0);
    expect(sessionCookieOptions("2001-01-01T00:00:00Z").maxAge).toBe(0);
  });

  it("is only sent over https in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(sessionCookieOptions(undefined).secure).toBe(true);
  });
});
