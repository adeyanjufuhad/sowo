import Link from "next/link";
import { ButtonLink } from "@/components/ui/button";
import { Logo } from "./logo";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#replay", label: "See a sale" },
  { href: "#features", label: "Features" },
  { href: "#trust", label: "Why Sowo" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-transparent bg-paper/85 backdrop-blur-md supports-[backdrop-filter]:bg-paper/70">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-paper"
      >
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Sowo home" className="rounded-full">
          <Logo />
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-full px-3 py-2 text-sm text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="hidden h-9 items-center rounded-full px-3 text-sm text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink sm:inline-flex"
          >
            Log in
          </Link>
          <ButtonLink href="/signup" size="sm">
            Start selling
          </ButtonLink>
        </div>
      </div>
    </header>
  );
}
