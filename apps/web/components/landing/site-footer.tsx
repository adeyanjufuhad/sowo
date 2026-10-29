import Link from "next/link";
import { BRAND_NAME, GITHUB_URL } from "@/lib/site";
import { Logo } from "./logo";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "Visit a demo shop", href: "/try" },
      { label: "Vendor dashboard", href: "/dashboard" },
      { label: "How it works", href: "/#how-it-works" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Log in", href: "/login" },
      { label: "Create an account", href: "/signup" },
      { label: "Privacy", href: "/privacy" },
    ],
  },
  {
    title: "Open source",
    links: [
      { label: "GitHub", href: GITHUB_URL, external: true },
      { label: "API contract", href: `${GITHUB_URL}/blob/main/docs/api-contract.md`, external: true },
      { label: "MIT licence", href: `${GITHUB_URL}/blob/main/LICENSE`, external: true },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto overflow-hidden bg-night text-paper">
      <div className="mx-auto max-w-6xl px-4 pt-16 sm:px-6 sm:pt-20">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr_1.2fr]">
          <div>
            <Logo tone="paper" />
            <p className="mt-4 max-w-[34ch] text-sm leading-relaxed text-paper/60">
              An AI sales assistant for vendors who sell on WhatsApp. Made in Nigeria.
            </p>
          </div>

          {COLUMNS.map((column) => (
            <nav key={column.title} aria-label={column.title}>
              <p className="text-xs font-medium tracking-[0.18em] text-paper/40 uppercase">{column.title}</p>
              <ul className="mt-4 space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.label}>
                    {"external" in link ? (
                      <a href={link.href} target="_blank" rel="noreferrer" className="text-sm text-paper/80 transition-colors hover:text-paper">
                        {link.label}
                      </a>
                    ) : (
                      <Link href={link.href} className="text-sm text-paper/80 transition-colors hover:text-paper">
                        {link.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-2 border-t border-paper/10 py-6 text-xs text-paper/40 sm:flex-row sm:justify-between">
          <p>© 2026 {BRAND_NAME}. MIT licensed.</p>
          <p>{BRAND_NAME} — Yoruba for “to trade”.</p>
        </div>
      </div>

      {/* Oversized wordmark, cropped by the bottom edge */}
      <p
        aria-hidden
        lang="yo"
        className="pointer-events-none -mb-[0.3em] text-center font-display text-[22vw] leading-[0.9] font-bold tracking-[-0.05em] text-paper/[0.06] select-none"
      >
        {BRAND_NAME}
      </p>
    </footer>
  );
}
