import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Open your shop on Sowo and let it sell on WhatsApp while you sleep.",
};

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh" aria-hidden />}>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
