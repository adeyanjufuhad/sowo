// Helpers for the server-side proxy that sits between the browser and the Sowo API (app/api/proxy).
// The session token lives in an httpOnly cookie on this site's domain; the browser never sees it and never
// talks to the API directly. Nothing here is imported by client code.

export const SESSION_COOKIE = "sowo_session";

/** Only these parts of the API are reachable through the proxy. Webhooks, for one, are not. */
const PROXIED = new Set(["auth", "conversations", "orders", "products", "simulator"]);

/** Where the proxy sends requests: the API's address as seen from this server. */
export function backendUrl(): string | null {
  const url = (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
  return url || null;
}

export function isProxiedPath(segments: string[]): boolean {
  if (segments.length === 0) return false;
  if (segments.some((segment) => segment === "" || segment === "." || segment === ".." || segment.includes("\\"))) {
    return false;
  }
  return PROXIED.has(segments[0]);
}

/** Browsers send Origin on cross-site POSTs. A request from another site must not act on the vendor's session. */
export function isSameOrigin(origin: string | null, host: string | null): boolean {
  if (!origin) return true; // not a browser cross-site request (curl, server to server, some same-site GETs)
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export function sessionCookieOptions(expiresAt: string | undefined) {
  const expires = expiresAt ? new Date(expiresAt) : null;
  const maxAge = expires && !Number.isNaN(expires.getTime()) ? Math.floor((expires.getTime() - Date.now()) / 1000) : 0;
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: Math.max(0, Math.min(maxAge, 60 * 60 * 24 * 30)),
  };
}
