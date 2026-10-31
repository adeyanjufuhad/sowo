import { NextResponse, type NextRequest } from "next/server";
import {
  backendUrl,
  isProxiedPath,
  isSameOrigin,
  SESSION_COOKIE,
  sessionCookieOptions,
} from "@/lib/session-proxy";

// The browser calls /api/proxy/<api path>. This handler adds the vendor's session (kept in an httpOnly cookie on
// this domain) as a bearer token and forwards the call to the Sowo API, so the token never reaches page scripts.

type Context = { params: Promise<{ path: string[] }> };

function failure(status: number, code: string, message: string) {
  return NextResponse.json({ error: { code, message } }, { status });
}

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params;
  const base = backendUrl();
  if (!base) return failure(503, "INTERNAL", "The API address is not configured (set API_INTERNAL_URL)");
  if (!isProxiedPath(path)) return failure(404, "NOT_FOUND", "Not found");
  if (request.method !== "GET" && !isSameOrigin(request.headers.get("origin"), request.headers.get("host"))) {
    return failure(403, "FORBIDDEN", "Cross-site requests are not allowed");
  }

  const route = path.join("/");
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  // Tell the API who the visitor is, or it would see every sign-in coming from this server. It only uses this when
  // its CLIENT_IP_HEADER is set, which it should be only when this server is the sole way to reach it.
  const visitor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || request.headers.get("x-real-ip");
  if (visitor) headers.set("x-forwarded-for", visitor);

  let upstream: Response;
  try {
    upstream = await fetch(`${base}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
    });
  } catch {
    return failure(502, "INTERNAL", "Couldn't reach the Sowo API");
  }
  // Bytes, not text: product pictures come back through here too, and decoding them as text would mangle them.
  const body = await upstream.arrayBuffer();

  // Signing in or up: keep the token in the cookie and hand the page only the vendor.
  if ((route === "auth/login" || route === "auth/signup") && upstream.ok) {
    try {
      const text = new TextDecoder().decode(body);
      const { sessionToken, expiresAt, ...rest } = JSON.parse(text) as { sessionToken: string; expiresAt?: string };
      const response = NextResponse.json(rest, { status: upstream.status });
      response.cookies.set(SESSION_COOKIE, sessionToken, sessionCookieOptions(expiresAt));
      return response;
    } catch {
      return failure(502, "INTERNAL", "The API sent an unexpected sign-in response");
    }
  }

  // 204 and friends must not carry a body, even an empty one.
  const bodyless = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
  const responseHeaders = new Headers({ "content-type": upstream.headers.get("content-type") ?? "application/json" });
  // Pictures never change once uploaded, so browsers may keep them; and they must not be sniffed as anything else.
  for (const name of ["cache-control", "x-content-type-options"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  const response = new NextResponse(bodyless ? null : body, { status: upstream.status, headers: responseHeaders });
  // Signed out, or the API says the session is gone: forget the cookie so the next page asks for a sign-in.
  const sessionEnded = route === "auth/logout" || (upstream.status === 401 && token && route !== "auth/login");
  if (sessionEnded) response.cookies.delete(SESSION_COOKIE);
  return response;
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST };
