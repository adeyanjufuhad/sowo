/** "21:41" in West Africa Time (UTC+1, no daylight saving), computed by hand so server and browser agree. */
export function watTime(iso: string): string {
  const date = new Date(iso);
  const hours = (date.getUTCHours() + 1) % 24;
  return `${String(hours).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}`;
}

/** "now", "4 min", "2 h", then "Yesterday" or "27 Oct" for older timestamps (West Africa Time). */
export function relativeTime(iso: string, nowMs: number): string {
  const diff = Math.max(0, nowMs - Date.parse(iso));
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  if (hours < 48) return "Yesterday";
  const date = new Date(Date.parse(iso) + 60 * 60_000);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${date.getUTCDate()} ${months[date.getUTCMonth()]}`;
}

/** "Kelechi O." -> "KO" */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
