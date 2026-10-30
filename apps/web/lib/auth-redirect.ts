// Pages anyone can use without an account. A 401 on these pages must not send the visitor to sign-in.
// The buyer simulator polls vendor endpoints so a signed-in vendor sees her own replies and "Mark paid" arrive
// live; for a visitor without a session those polls answer 401, and the chat should simply carry on.
const PUBLIC_PATHS = ["/try"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

/** Whether a 401 from `endpointPath`, seen while the browser is on `pathname`, should go to the sign-in page. */
export function shouldRedirectToLogin(endpointPath: string, pathname: string): boolean {
  if (endpointPath.startsWith("/auth/")) return false;
  return !isPublicPath(pathname);
}
