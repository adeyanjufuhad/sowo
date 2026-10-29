import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "@/components/landing/logo";
import { SiteFooter } from "@/components/landing/site-footer";
import { GITHUB_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What Sowo keeps, who sees it, and how to have it deleted.",
};

const LAST_UPDATED = "29 October 2026";

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "What a buyer's message brings with it",
    body: [
      "A buyer's WhatsApp phone number, the name they give us, and the messages they send.",
      "The orders that come out of those messages: the items, the delivery area, the price the server agreed, and whether the buyer said they had paid by bank transfer.",
    ],
  },
  {
    title: "What a vendor hands over",
    body: [
      "The vendor's email address, shop settings (owner name, WhatsApp number ID, alert phone), and the bank details shown to buyers when payment is by bank transfer.",
      "Product listings and the floor prices the assistant is not allowed to go below.",
    ],
  },
  {
    title: "Who reads the conversation",
    body: [
      "The vendor, in their dashboard, and the open-weight Qwen3 model served through Groq, which drafts each reply. A message is sent to that model only to answer it.",
      "We do not sell data and we do not use buyer messages to train a model.",
    ],
  },
  {
    title: "Money",
    body: [
      "Bank transfers happen between the buyer and the vendor, outside Sowo. A buyer's receipt is a note on the order, not a payment.",
      "When card payment is switched on, Paystack handles the card and Sowo never sees the card number.",
    ],
  },
  {
    title: "Where it lives",
    body: [
      "In a Postgres database hosted by Neon (AWS, London) and a web service on Render. The site itself is served by Vercel.",
      "Access tokens and app secrets are held as environment variables, never in the code, and the source is public.",
    ],
  },
  {
    title: "Keeping it, deleting it",
    body: [
      "Conversations and orders are kept while the shop uses Sowo, so the vendor can look back at a sale.",
      "Ask for your shop and its conversations to be deleted and we remove them. Open an issue on GitHub and we will take it from there.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <>
      <header className="border-b border-line/80 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link href="/" aria-label="Sowo home" className="rounded-full">
            <Logo />
          </Link>
          <Link href="/" className="text-sm font-semibold text-muted transition-colors hover:text-ink">
            Back to Sowo
          </Link>
        </div>
      </header>
      <main id="main" className="flex-1 px-4 py-14 sm:px-6 sm:py-20">
        <article className="mx-auto max-w-3xl">
          <p className="text-xs font-medium tracking-[0.18em] text-muted uppercase">Privacy</p>
          <h1 className="font-display mt-3 text-4xl leading-tight text-ink sm:text-5xl">What Sowo keeps</h1>
          <p className="mt-5 max-w-[62ch] text-base leading-relaxed text-muted">
            Sowo answers buyers on WhatsApp for a vendor&apos;s shop. This page says, plainly, what it stores to do
            that, who else sees it, and how to have it deleted.
          </p>
          <p className="mt-2 text-sm text-muted">Last updated {LAST_UPDATED}.</p>

          <div className="mt-12 space-y-10">
            {SECTIONS.map((section) => (
              <section key={section.title} aria-labelledby={section.title} className="border-t border-line pt-8">
                <h2 id={section.title} className="font-display text-xl text-ink">
                  {section.title}
                </h2>
                {section.body.map((paragraph) => (
                  <p key={paragraph} className="mt-3 max-w-[62ch] text-base leading-relaxed text-muted">
                    {paragraph}
                  </p>
                ))}
              </section>
            ))}
            <section aria-labelledby="questions" className="border-t border-line pt-8">
              <h2 id="questions" className="font-display text-xl text-ink">
                Questions
              </h2>
              <p className="mt-3 max-w-[62ch] text-base leading-relaxed text-muted">
                Sowo is open source. Open an issue at{" "}
                <a
                  href={`${GITHUB_URL}/issues`}
                  className="font-semibold text-ink underline decoration-mustard decoration-2 underline-offset-4"
                >
                  {GITHUB_URL.replace("https://", "")}/issues
                </a>{" "}
                and we will answer there.
              </p>
            </section>
          </div>
        </article>
      </main>
      <SiteFooter />
    </>
  );
}
