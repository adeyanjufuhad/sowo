"use client";

import { useEffect } from "react";

/** Nudges a sleeping API awake as soon as any page opens. Renders nothing. */
export function WakeApi() {
  useEffect(() => {
    // Read here rather than from lib/api, which would pull the in-browser mock into every page.
    if (!process.env.NEXT_PUBLIC_API_URL?.trim()) return;
    fetch("/api/wake", { cache: "no-store" }).catch(() => {});
  }, []);
  return null;
}
