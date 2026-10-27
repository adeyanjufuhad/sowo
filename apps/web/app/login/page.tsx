import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your Sowo vendor dashboard.",
};

export default function LoginPage() {
  return (
    // The form reads ?next from the URL, so it renders on the client.
    <Suspense fallback={<div className="min-h-dvh" aria-hidden />}>
      <AuthForm mode="login" />
    </Suspense>
  );
}
