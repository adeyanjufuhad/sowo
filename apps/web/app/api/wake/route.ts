import { connection, NextResponse } from "next/server";
import { backendUrl } from "@/lib/session-proxy";

// Render's free API sleeps after 15 quiet minutes and takes up to a minute to wake. Every page asks for this once
// on load (components/wake-api.tsx), so someone who opens the landing page has a warm API by the time they reach
// /try or sign in. The request to /health is what wakes it; this handler doesn't wait out a cold start.

export async function GET() {
  await connection(); // per request, never prerendered at build time
  const base = backendUrl();
  if (!base) return new NextResponse(null, { status: 204 });
  try {
    const upstream = await fetch(`${base}/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    return NextResponse.json({ awake: upstream.ok }, { status: upstream.ok ? 200 : 202 });
  } catch {
    return NextResponse.json({ awake: false }, { status: 202 }); // still waking; the request has already reached it
  }
}
