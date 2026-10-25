// Seeded conversations for Ada's Footwear. Most are produced by running the same
// agent and server tools the simulator uses, so the seed can't drift from the logic.

import type { Message } from "@sowo/shared";
import {
  createEmptyState,
  listMessages,
  receiveBuyerMessage,
  sendVendorReply,
  settlePayment,
  type MockState,
} from "./store";

const MINUTE = 60_000;

type Step =
  | { buyer: string }
  | { vendor: string }
  | { pay: "SUCCESS" | "FAILED" };

function play(state: MockState, customerName: string, startedMinutesAgo: number, steps: Step[], now: Date): string {
  let conversationId: string | undefined;
  let at = now.getTime() - startedMinutesAgo * MINUTE;

  for (const step of steps) {
    const when = new Date(at);
    if ("buyer" in step) {
      const result = receiveBuyerMessage(state, { conversationId, customerName, platform: "WHATSAPP", body: step.buyer }, when);
      conversationId = result.conversation.id;
    } else if ("vendor" in step && conversationId) {
      sendVendorReply(state, conversationId, step.vendor, when);
    } else if ("pay" in step && conversationId) {
      const pending = state.orders.find((o) => o.conversationId === conversationId && o.paymentStatus === "PENDING");
      if (pending?.paymentReference) settlePayment(state, pending.paymentReference, step.pay, when);
    }
    at += MINUTE;
  }
  return conversationId as string;
}

/** The headline sale: 35k offer, ₦43,000 counter, 41k accepted, ₦2,500 to Ikeja, ₦43,500 paid. */
export const LOAFERS_SALE: Step[] = [
  { buyer: "Good evening. How much for the black loafers? Size 43" },
  { buyer: "Abeg do am 35k" },
  { buyer: "Make it 41 na" },
  { buyer: "Ikeja, Allen Avenue" },
  { pay: "SUCCESS" },
];

export function createSeedState(now: Date = new Date()): MockState {
  const state = createEmptyState();

  const ngozi = play(state, "Ngozi E.", 2 * 24 * 60, [
    { buyer: "Hello, do you have the Ankara block heels?" },
    { buyer: "I'll take it. Deliver to Yaba please" },
    { pay: "SUCCESS" },
  ], now);

  play(state, "Tobi A.", 26 * 60, [
    { buyer: "How much be the tan palm slippers?" },
    { buyer: "Abeg 15k" },
    { buyer: "I dey Surulere" },
    { pay: "FAILED" },
  ], now);

  play(state, "Kelechi O.", 42, LOAFERS_SALE, now);

  play(state, "Funke A.", 25, [
    { buyer: "Good afternoon. I bought the nude heels last week but size 38 is too tight. Can I exchange it for 39?" },
  ], now);

  play(state, "Blessing E.", 18, [
    { buyer: "Hello! I need 6 pairs of the beaded aso-oke slides for my sister's wedding, different sizes. Can you give me a discount?" },
    { vendor: "Hi Blessing, Ada here. Congratulations to your sister! For 6 pairs I can do ₦19,500 each. Send me the sizes." },
    { buyer: "Thank you ma! Sizes 38, 39, 39, 40, 41 and 42." },
  ], now);

  play(state, "Seun B.", 9, [
    { buyer: "Do you have the brown chelsea boots in size 43?" },
    { buyer: "Can you do 50k?" },
    { buyer: "Lekki Phase 1" },
  ], now);

  play(state, "Ibrahim M.", 3, [{ buyer: "Abeg you get white sneakers size 44?" }], now);

  // Later fulfilment for the older sale.
  const delivered = state.orders.find((o) => o.conversationId === ngozi);
  if (delivered) delivered.fulfillmentStatus = "DELIVERED";

  return state;
}

/** The loafers sale on its own, for the landing page replay. Fixed date so it renders identically everywhere. */
export function loafersDemoMessages(): Message[] {
  const state = createEmptyState();
  const id = play(state, "Kelechi O.", 0, LOAFERS_SALE, new Date("2026-10-27T19:41:00.000Z"));
  return listMessages(state, id).messages;
}
