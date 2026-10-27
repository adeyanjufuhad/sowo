import type { Metadata } from "next";
import { Suspense } from "react";
import { AppHeader } from "@/components/app-header";
import { AccountBar } from "@/components/auth/account-bar";
import { Dashboard } from "@/components/dashboard/dashboard";

export const metadata: Metadata = {
  title: "Vendor dashboard",
  description: "Ada's Footwear: chats Sowo is handling, orders to pack, and products with price, floor and stock.",
};

export default function DashboardPage() {
  return (
    <>
      <AppHeader current="/dashboard" />
      <AccountBar />
      <main id="main" className="flex-1">
        {/* The dashboard reads ?tab and ?chat from the URL, so it renders on the client */}
        <Suspense fallback={<div className="mx-auto h-96 max-w-7xl animate-pulse px-6 py-8" aria-hidden />}>
          <Dashboard />
        </Suspense>
      </main>
    </>
  );
}
