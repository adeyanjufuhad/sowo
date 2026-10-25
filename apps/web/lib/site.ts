// Site-wide constants for the landing page and footer.

export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com";

export const EVENT_NAME = "OSCA OPEN//BUILD 2026";

/** Shown in the footer. Fill in names and roles before submission. */
export const TEAM: { name: string; role: string }[] = [
  { name: "Frontend lead", role: "Web app, design" },
  { name: "Backend lead", role: "API, model, payments" },
];
