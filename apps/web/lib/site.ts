// Site-wide constants for the landing page and footer.

export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/adeyanjufuhad/sowo";

export const EVENT_NAME = "OSCA OPEN//BUILD 2026";

/** Shown in the footer. Keep in step with the Team section of the README. */
export const TEAM: { name: string; role: string }[] = [
  { name: "Fuhad Adeyanju", role: "Frontend, design" },
  { name: "@0xAlpha01", role: "Backend, model, payments" },
];
