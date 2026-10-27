import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import { AccountBar } from "@/components/auth/account-bar";
import { SettingsForm } from "@/components/settings/settings-form";

export const metadata: Metadata = {
  title: "Shop settings",
  description: "Connect your WhatsApp number, choose where alerts go and how buyers pay you.",
};

export default function SettingsPage() {
  return (
    <>
      <AppHeader current="/dashboard" />
      <AccountBar />
      <main id="main" className="flex-1">
        <SettingsForm />
      </main>
    </>
  );
}
