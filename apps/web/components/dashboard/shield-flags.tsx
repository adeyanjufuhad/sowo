"use client";

import type { ShieldFlag } from "@sowo/shared";
import { ShieldAlert } from "lucide-react";
import { useState } from "react";
import { api, ApiRequestError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Scam Shield's open warnings for one chat, each with a Resolve button once the vendor has checked. */
export function ShieldFlags({
  conversationId,
  flags,
  onResolved,
}: {
  conversationId: string;
  flags: ShieldFlag[];
  onResolved: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function resolve(flag: ShieldFlag) {
    setBusy(flag.id);
    setError(null);
    try {
      await api.resolveFlag(conversationId, flag.id);
      onResolved();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't resolve that. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-label="Scam Shield warnings" className="space-y-2 border-b border-line bg-[#fdecea] px-4 py-3">
      {flags.map((flag) => (
        <div key={flag.id} role="alert" className="flex items-start gap-2.5 text-sm text-[#7a1a14]">
          <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" strokeWidth={2} />
          <div className="min-w-0 flex-1">
            <p className={cn("font-semibold", flag.severity === "high" && "uppercase tracking-wide")}>
              {flag.severity === "high" ? "Possible scam. " : ""}
              {flag.warning}
            </p>
            <p className="mt-0.5 truncate text-xs text-[#7a1a14]/80">They wrote: “{flag.evidence}”</p>
          </div>
          <button
            type="button"
            onClick={() => void resolve(flag)}
            disabled={busy === flag.id}
            className="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#7a1a14] ring-1 ring-[#e6b4ae] transition-colors hover:bg-[#fff6f5] disabled:opacity-60"
          >
            Resolve
          </button>
        </div>
      ))}
      {error ? <p className="text-xs text-[#7a1a14]">{error}</p> : null}
    </section>
  );
}
