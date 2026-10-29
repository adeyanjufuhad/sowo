import { BRAND_NAME } from "@/lib/site";
import { cn } from "@/lib/utils";

/** Sowo wordmark: a terracotta speech bubble with a smile, then the name with its Yoruba tone marks. */
export function Logo({ className, tone = "ink" }: { className?: string; tone?: "ink" | "paper" }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <svg viewBox="0 0 32 32" aria-hidden className="size-7 shrink-0">
        <path
          d="M16 3.5c7.2 0 12.5 4.9 12.5 11.2 0 6.3-5.3 11.2-12.5 11.2-1.4 0-2.7-.2-4-.5L6 28.5l1.6-5.4C5 21 3.5 18 3.5 14.7 3.5 8.4 8.8 3.5 16 3.5Z"
          fill="var(--accent)"
        />
        <circle cx="12" cy="13.5" r="1.6" fill="var(--night)" />
        <circle cx="20" cy="13.5" r="1.6" fill="var(--night)" />
        <path d="M12.5 17.6c1.9 1.7 5.1 1.7 7 0" stroke="var(--night)" strokeWidth="1.6" strokeLinecap="round" fill="none" />
      </svg>
      <span
        lang="yo"
        className={cn(
          "font-display text-[22px] leading-none font-bold tracking-[-0.03em]",
          tone === "ink" ? "text-ink" : "text-paper",
        )}
      >
        {BRAND_NAME}
      </span>
    </span>
  );
}
