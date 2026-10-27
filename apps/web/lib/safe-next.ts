/** Where to go after signing in. Only paths on this site: never `//evil.example` or `https://...`. */
export function safeNext(value: string | null | undefined, fallback = "/dashboard"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
  if (/^\/(login|signup)(\/|\?|$)/.test(value)) return fallback;
  return value;
}
