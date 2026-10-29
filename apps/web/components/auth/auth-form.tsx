"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Logo } from "@/components/landing/logo";
import { api, ApiRequestError, USING_MOCK } from "@/lib/api";
import { safeNext } from "@/lib/safe-next";

const field =
  "h-11 w-full rounded-xl bg-paper px-3.5 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong";

/** The sign-in and sign-up card. They are the same form; sign-up also asks for a business name. */
export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const ids = { name: useId(), email: useId(), password: useId() };
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const signup = mode === "signup";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (signup) await api.signup({ email, password, businessName });
      else await api.login({ email, password });
      router.replace(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't reach the server. Check your connection and try again.");
      setBusy(false);
    }
  }

  return (
    <main id="main" className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Link href="/" aria-label="Sowo home" className="mb-6 flex justify-center rounded-full">
          <Logo />
        </Link>
        <div className="rounded-3xl bg-card p-6 ring-1 ring-line sm:p-7">
          <h1 className="font-display text-2xl font-semibold tracking-[-0.03em]">
            {signup ? "Open your shop on Sowo" : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            {signup ? "Create a vendor account to run your WhatsApp sales from the dashboard." : "Sign in to see your chats, orders and products."}
          </p>

          {USING_MOCK ? (
            <p role="status" className="mt-5 rounded-xl bg-paper-deep px-3.5 py-3 text-sm text-ink-soft">
              This copy of Sowo runs in demo mode without a backend, so there are no accounts.{" "}
              <Link href="/dashboard" className="font-medium text-accent-strong underline-offset-4 hover:underline">
                Open the demo dashboard
              </Link>
              .
            </p>
          ) : (
            <form onSubmit={submit} className="mt-5 space-y-4">
              {signup ? (
                <div>
                  <label htmlFor={ids.name} className="mb-1.5 block text-sm font-medium">
                    Business name
                  </label>
                  <input
                    id={ids.name}
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    autoComplete="organization"
                    required
                    maxLength={120}
                    placeholder="Ada's Footwear"
                    className={field}
                  />
                </div>
              ) : null}
              <div>
                <label htmlFor={ids.email} className="mb-1.5 block text-sm font-medium">
                  Email
                </label>
                <input
                  id={ids.email}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  placeholder="you@example.com"
                  className={field}
                />
              </div>
              <div>
                <label htmlFor={ids.password} className="mb-1.5 block text-sm font-medium">
                  Password
                </label>
                <div className="relative">
                  <input
                    id={ids.password}
                    type={passwordVisible ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={signup ? "new-password" : "current-password"}
                    required
                    minLength={signup ? 10 : undefined}
                    maxLength={128}
                    className={`${field} pr-12`}
                  />
                  <button
                    type="button"
                    aria-label={passwordVisible ? "Hide password" : "Show password"}
                    aria-controls={ids.password}
                    onClick={() => setPasswordVisible((visible) => !visible)}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
                  >
                    {passwordVisible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                  </button>
                </div>
                {signup ? <p className="mt-1.5 text-xs text-muted">At least 10 characters.</p> : null}
              </div>

              {error ? (
                <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-full bg-accent-strong px-4 text-sm font-medium text-white transition-[transform,background-color] hover:bg-[#a33515] active:scale-[0.99] disabled:opacity-60"
              >
                {busy ? (signup ? "Creating your account…" : "Signing in…") : signup ? "Create account" : "Sign in"}
              </button>
            </form>
          )}
        </div>
        <p className="mt-5 text-center text-sm text-muted">
          {signup ? "Already have an account? " : "New to Sowo? "}
          <Link
            href={signup ? "/login" : "/signup"}
            className="font-medium text-accent-strong underline-offset-4 hover:underline"
          >
            {signup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </div>
    </main>
  );
}
