import Link from "next/link";
import { EVENT_NAME, GITHUB_URL, TEAM } from "@/lib/site";
import { Logo } from "./logo";

export function SiteFooter() {
  const columns = [
    {
      title: "Product",
      links: [
        { label: "Live demo", href: "/try" },
        { label: "Vendor dashboard", href: "/dashboard" },
        { label: "How it works", href: "/#how-it-works" },
      ],
    },
    {
      title: "Project",
      links: [
        { label: "GitHub", href: GITHUB_URL, external: true },
        { label: "API contract", href: `${GITHUB_URL}/blob/main/docs/api-contract.md`, external: true },
        { label: "MIT licence", href: `${GITHUB_URL}/blob/main/LICENSE`, external: true },
      ],
    },
  ];

  return (
    <footer className="mt-auto overflow-hidden bg-night text-paper">
      <div className="mx-auto max-w-6xl px-4 pt-16 sm:px-6 sm:pt-20">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr_1.2fr]">
          <div>
            <Logo tone="paper" />
            <p className="mt-4 max-w-[34ch] text-sm leading-relaxed text-paper/60">
              An AI sales assistant for Nigerian vendors on WhatsApp. Built for {EVENT_NAME} by OSCA Ile-Ife.
            </p>
          </div>

          {columns.map((column) => (
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

          <div>
            <p className="text-xs font-medium tracking-[0.18em] text-paper/40 uppercase">Team</p>
            <ul className="mt-4 space-y-2.5">
              {TEAM.map((member) => (
                <li key={member.name} className="text-sm">
                  <span className="text-paper/80">{member.name}</span>
                  <span className="text-paper/40"> · {member.role}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-16 flex flex-col gap-2 border-t border-paper/10 py-6 text-xs text-paper/40 sm:flex-row sm:justify-between">
          <p>MIT licensed. Clay illustrations generated with Google Flow.</p>
          <p>Sowo dey sell while you sleep.</p>
        </div>
      </div>

      {/* Oversized wordmark, cropped by the bottom edge */}
      <p
        aria-hidden
        className="pointer-events-none -mb-[0.28em] text-center font-display text-[32vw] leading-[0.8] font-bold tracking-[-0.07em] text-paper/[0.06] select-none"
      >
        sowo
      </p>
    </footer>
  );
}
