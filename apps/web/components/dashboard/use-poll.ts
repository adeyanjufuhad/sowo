"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiRequestError } from "@/lib/api";

export const POLL_MS = 3000;

/**
 * Load data, then refresh it every 3 seconds while the tab is visible.
 * `key` restarts the cycle (e.g. a different conversation); null pauses it.
 */
export function usePoll<T>(load: (() => Promise<T>) | null, key: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  const refresh = useCallback(async () => {
    const run = loadRef.current;
    if (!run) return;
    try {
      const next = await run();
      setData(next);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't reach the server. Retrying…");
    }
  }, []);

  useEffect(() => {
    if (key === null) return;
    const first = window.setTimeout(refresh, 0);
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, POLL_MS);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [key, refresh]);

  return { data, error, refresh, setData };
}
