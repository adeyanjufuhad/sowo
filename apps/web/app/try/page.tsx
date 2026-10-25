import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import { Simulator } from "@/components/try/simulator";

export const metadata: Metadata = {
  title: "Buyer simulator",
  description: "Haggle with Sowo as a buyer and see every tool call the model makes and every price the server decides.",
};

export default function TryPage() {
  return (
    <>
      <AppHeader current="/try" />
      <main id="main" className="flex-1">
        <h1 className="sr-only">Buyer simulator</h1>
        <Simulator />
      </main>
    </>
  );
}
