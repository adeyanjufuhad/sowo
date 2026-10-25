/** "21:41" in West Africa Time (UTC+1, no daylight saving), computed by hand so server and browser agree. */
export function watTime(iso: string): string {
  const date = new Date(iso);
  const hours = (date.getUTCHours() + 1) % 24;
  return `${String(hours).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}`;
}
