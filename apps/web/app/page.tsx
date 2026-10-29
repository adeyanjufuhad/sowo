import { ClickSpark } from "@/components/landing/click-spark";
import { ClosingCta } from "@/components/landing/closing-cta";
import { Features } from "@/components/landing/features";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Problem } from "@/components/landing/problem";
import { EngineSection } from "@/components/landing/engine-section";
import { ReplaySection } from "@/components/landing/replay-section";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { StackStrip } from "@/components/landing/stack-strip";
import { Trust } from "@/components/landing/trust";
import { loafersDemoMessages } from "@/lib/mock/seed";

export default function Home() {
  // Same agent and server code as the simulator, run once with a fixed date.
  const messages = loafersDemoMessages();

  return (
    <>
      <ClickSpark />
      <SiteHeader />
      <main id="main">
        <Hero />
        <StackStrip />
        <Problem />
        <HowItWorks />
        <ReplaySection messages={messages} />
        <EngineSection />
        <Features />
        <Trust />
        <ClosingCta />
      </main>
      <SiteFooter />
    </>
  );
}
