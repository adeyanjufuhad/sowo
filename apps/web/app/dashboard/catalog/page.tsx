import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import { AccountBar } from "@/components/auth/account-bar";
import { CatalogManager } from "@/components/catalog/catalog-manager";

export const metadata: Metadata = {
  title: "Your catalog",
  description: "Add and edit the products you sell and the areas you deliver to.",
};

export default function CatalogPage() {
  return (
    <>
      <AppHeader current="/dashboard" />
      <AccountBar />
      <main id="main" className="flex-1">
        <CatalogManager />
      </main>
    </>
  );
}
