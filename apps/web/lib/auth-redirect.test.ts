import { describe, expect, it } from "vitest";
import { shouldRedirectToLogin } from "./auth-redirect";

describe("shouldRedirectToLogin", () => {
  it("sends a signed-out vendor on the dashboard to sign in", () => {
    expect(shouldRedirectToLogin("/conversations", "/dashboard")).toBe(true);
    expect(shouldRedirectToLogin("/orders", "/dashboard/orders")).toBe(true);
  });

  it("keeps a visitor on the buyer simulator when its polls answer 401", () => {
    expect(shouldRedirectToLogin("/conversations/c1/messages", "/try")).toBe(false);
    expect(shouldRedirectToLogin("/orders", "/try")).toBe(false);
  });

  it("does not treat lookalike paths as the simulator", () => {
    expect(shouldRedirectToLogin("/orders", "/tryouts")).toBe(true);
  });

  it("never redirects for the sign-in endpoints themselves", () => {
    expect(shouldRedirectToLogin("/auth/me", "/dashboard")).toBe(false);
  });
});
