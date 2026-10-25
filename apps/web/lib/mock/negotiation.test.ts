import { describe, expect, it } from "vitest";
import { NO_OFFERS_YET, evaluateOffer, findDeliveryArea, parseOfferKobo } from "./negotiation";
import { createEmptyState, listMessages, receiveBuyerMessage, settlePayment } from "./store";
import { createSeedState } from "./seed";

const loafers = { basePriceKobo: 4_500_000, floorPriceKobo: 4_000_000 };

describe("evaluateOffer", () => {
  it("counters 35k with ₦43,000, then accepts 41k", () => {
    const first = evaluateOffer(loafers, 3_500_000, NO_OFFERS_YET);
    expect(first.output).toEqual({ decision: "COUNTER", counterKobo: 4_300_000 });

    const second = evaluateOffer(loafers, 4_100_000, first.history);
    expect(second.output).toEqual({ decision: "ACCEPT", agreedPriceKobo: 4_100_000 });
  });

  it("comes down in steps, never below the floor, then holds", () => {
    let history = NO_OFFERS_YET;
    const counters: number[] = [];
    for (let i = 0; i < 4; i++) {
      const result = evaluateOffer(loafers, 3_000_000, history);
      history = result.history;
      counters.push(result.output.counterKobo ?? 0);
    }
    expect(counters).toEqual([4_300_000, 4_150_000, 4_000_000, 4_000_000]);
    expect(evaluateOffer(loafers, 3_000_000, history).output.decision).toBe("HOLD");
  });

  it("never charges more than the base price", () => {
    expect(evaluateOffer(loafers, 5_000_000, NO_OFFERS_YET).output.agreedPriceKobo).toBe(4_500_000);
  });
});

describe("parseOfferKobo", () => {
  it.each([
    ["Abeg do am 35k", 3_500_000],
    ["Make it 41 na", 4_100_000],
    ["Can you do ₦41,000?", 4_100_000],
    ["I fit pay 40 thousand for size 43", 4_000_000],
    ["last price 38500", 3_850_000],
  ])("%s", (text, kobo) => {
    expect(parseOfferKobo(text)).toBe(kobo);
  });

  it("ignores shoe sizes", () => {
    expect(parseOfferKobo("Na size 43")).toBeUndefined();
  });
});

describe("findDeliveryArea", () => {
  it("finds Lagos areas in free text", () => {
    expect(findDeliveryArea("Ikeja, Allen Avenue")).toBe("Ikeja");
    expect(findDeliveryArea("I dey Lekki Phase 1")).toBe("Lekki");
    expect(findDeliveryArea("somewhere else")).toBeUndefined();
  });
});

describe("mock simulator", () => {
  it("runs the loafers sale end to end", () => {
    const state = createEmptyState();
    const now = new Date("2026-10-27T19:41:00.000Z");
    const send = (body: string, conversationId?: string) =>
      receiveBuyerMessage(state, { conversationId, platform: "SIMULATOR", body }, now);

    const { conversation } = send("How much for the black loafers?");
    const id = conversation.id;
    send("Na size 43", id);
    const counter = send("Abeg do am 35k", id).messages[1];
    expect(counter?.toolCalls?.[0]).toMatchObject({ tool: "evaluate_offer", output: { decision: "COUNTER", counterKobo: 4_300_000 } });
    expect(counter?.body).toContain("₦43,000");

    send("Make it 41 na", id);
    const quoteReply = send("I dey Ikeja", id).messages[1];
    const quote = quoteReply?.toolCalls?.find((c) => c.tool === "get_quote");
    expect(quote?.output).toMatchObject({ subtotalKobo: 4_100_000, deliveryFeeKobo: 250_000, totalKobo: 4_350_000 });
    expect(quoteReply?.body).toContain("₦43,500");

    const order = state.orders[0];
    expect(order).toMatchObject({ paymentStatus: "PENDING", totalKobo: 4_350_000 });
    expect(state.products.find((p) => p.id === "prod_loafer_blk_43")?.stockOnHand).toBe(2);

    const paid = settlePayment(state, order?.paymentReference ?? "", "SUCCESS", now);
    expect(paid.order).toMatchObject({ paymentStatus: "PAID", fulfillmentStatus: "PACKAGING" });
    expect(paid.messages[0]?.body).toContain("Receipt");
  });

  it("never puts the floor price in anything the model or buyer sees", () => {
    const state = createSeedState(new Date("2026-10-27T20:00:00.000Z"));
    const visible = JSON.stringify(state.messages);
    expect(visible).not.toMatch(/floor/i);
    for (const product of state.products) {
      expect(visible).not.toContain(`"counterKobo":${product.floorPriceKobo - 1}`);
    }
  });

  it("hands complaints to the vendor", () => {
    const state = createEmptyState();
    const { conversation } = receiveBuyerMessage(
      state,
      { platform: "SIMULATOR", body: "The heels are too tight, can I exchange them?" },
      new Date(),
    );
    expect(conversation.status).toBe("NEEDS_ATTENTION");
    const again = receiveBuyerMessage(state, { conversationId: conversation.id, platform: "SIMULATOR", body: "Hello?" }, new Date());
    expect(again.messages).toHaveLength(1);
  });

  it("seeds the loafers sale as a paid order", () => {
    const state = createSeedState(new Date("2026-10-27T20:00:00.000Z"));
    const kelechi = state.conversations.find((c) => c.customerName === "Kelechi O.");
    const order = state.orders.find((o) => o.conversationId === kelechi?.id);
    expect(order).toMatchObject({ totalKobo: 4_350_000, deliveryFeeKobo: 250_000, paymentStatus: "PAID" });
    expect(listMessages(state, kelechi?.id ?? "").messages.map((m) => m.sender)).toEqual([
      "BUYER", "AI", "BUYER", "AI", "BUYER", "AI", "BUYER", "AI", "AI",
    ]);
  });
});
