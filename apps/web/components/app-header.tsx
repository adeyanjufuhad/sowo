import Link from "next/link";
import { Logo } from "@/components/landing/logo";
import { USING_MOCK } from "@/lib/api";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/try", label: "Buyer simulator", short: "Buyer" },
  { href: "/dashboard", label: "Vendor dashboard", short: "Vendor" },
];

/** Compact header for the app pages (/try and /dashboard). */
export function AppHeader({ current }: { current: "/try" | "/dashboard" }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/85 shadow-[0_1px_12px_rgba(65,48,34,0.03)] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <Link href="/" aria-label="Sowo home" className="rounded-full transition-transform hover:-translate-y-0.5">
          <Logo />
        </Link>
        <nav aria-label="App" className="flex items-center gap-1 rounded-xl border border-line/70 bg-card/65 p-1 shadow-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={current === link.href ? "page" : undefined}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-all sm:text-sm",
                current === link.href ? "bg-night text-white shadow-sm" : "text-muted hover:bg-paper hover:text-ink",
              )}
            >
              <span className="sm:hidden">{link.short}</span>
              <span className="hidden sm:inline">{link.label}</span>
            </Link>
          ))}
        </nav>
        <span
          className="hidden items-center gap-1.5 rounded-full border border-line bg-card/70 px-3 py-1.5 text-[11px] font-medium text-muted md:inline-flex"
          title={USING_MOCK ? "No backend configured: a scripted stand-in plays the model, in your browser" : "Connected to the Sowo backend"}
        >
          <span aria-hidden className="size-1.5 rounded-full bg-mustard" />
          {USING_MOCK ? "Demo mode" : "Live backend"}
        </span>
      </div>
    </header>
  );
}
