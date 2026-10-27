import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/session-proxy";

// Sends visitors without a session to the sign-in page before the dashboard renders. This is a convenience, not
// the security check: the API validates the session on every data request and answers 401 if it is not valid.
export function proxy(request: NextRequest) {
  // Without a backend configured the dashboard runs on the in-browser demo data and has no accounts.
  if (!process.env.NEXT_PUBLIC_API_URL) return NextResponse.next();
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const login = new URL("/login", request.url);
  login.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
