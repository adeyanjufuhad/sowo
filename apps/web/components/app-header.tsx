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
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link href="/" aria-label="Sowo home" className="rounded-full">
          <Logo />
        </Link>
        <nav aria-label="App" className="flex items-center gap-1 rounded-full bg-paper-deep p-1">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={current === link.href ? "page" : undefined}
              className={cn(
                "rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors sm:text-sm",
                current === link.href ? "bg-card text-ink shadow-sm ring-1 ring-line" : "text-ink-soft hover:text-ink",
              )}
            >
              <span className="sm:hidden">{link.short}</span>
              <span className="hidden sm:inline">{link.label}</span>
            </Link>
          ))}
        </nav>
        <span
          className="hidden rounded-full bg-card px-2.5 py-1 text-[11px] font-medium text-muted ring-1 ring-line md:inline"
          title={USING_MOCK ? "No backend configured: a scripted stand-in plays the model, in your browser" : "Connected to the Sowo backend"}
        >
          {USING_MOCK ? "Demo mode" : "Live backend"}
        </span>
      </div>
    </header>
  );
}
