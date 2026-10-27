"use client";

import { LogOut, Settings } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, USING_MOCK } from "@/lib/api";

/** Who is signed in, with a way out. Shown only when the dashboard is talking to a real backend. */
export function AccountBar() {
  const [name, setName] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (USING_MOCK) return;
    api
      .me()
      .then((res) => setName(res.vendor.name))
      .catch(() => undefined); // a 401 sends the page to the sign-in screen by itself
  }, []);

  if (USING_MOCK) return null;

  async function signOut() {
    setLeaving(true);
    try {
      await api.logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="border-b border-line bg-paper-deep/50">
      <div className="mx-auto flex h-9 max-w-7xl items-center justify-end gap-3 px-4 text-xs text-ink-soft sm:px-6">
        {name ? <span>Signed in as <span className="font-medium text-ink">{name}</span></span> : null}
        <Link
          href="/dashboard/settings"
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
        >
          <Settings aria-hidden className="size-3.5" strokeWidth={2} /> Shop settings
        </Link>
        <button
          type="button"
          onClick={signOut}
          disabled={leaving}
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink disabled:opacity-60"
        >
          <LogOut aria-hidden className="size-3.5" strokeWidth={2} /> {leaving ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </div>
  );
}
