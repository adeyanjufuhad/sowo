// The scripted stand-in for Qwen3. Like the real model, it only reads the buyer's
// message, picks tools and phrases the reply. Every number it says comes from a
// tool output computed by the server (store.ts).

import { formatNaira } from "@sowo/shared";
import type {
  CatalogHit,
  EvaluateOfferCall,
  GetQuoteCall,
  RequestPaymentCall,
  SearchCatalogCall,
  ToolCall,
} from "@sowo/shared";
import { FAMILY_BY_PRODUCT_ID, SIZE_BY_PRODUCT_ID, VENDOR_OWNER, extractQuery } from "./catalog";
import { findDeliveryArea, parseOfferKobo } from "./negotiation";

export type Lang = "en" | "pcm";

/** What the agent remembers about a conversation between turns. */
export interface AgentMemory {
  lang: Lang;
  family?: string;
  productId?: string;
  deliveryArea?: string;
  /** Set once evaluate_offer accepts; the price itself lives on the server. */
  dealAgreed: boolean;
  awaitingPayment: boolean;
}

export const freshMemory = (): AgentMemory => ({
  lang: "en",
  dealAgreed: false,
  awaitingPayment: false,
});

export interface AgentTools {
  searchCatalog(query: string): SearchCatalogCall;
  evaluateOffer(productId: string, offerKobo: number): EvaluateOfferCall;
  getQuote(productId: string, deliveryArea: string): GetQuoteCall;
  requestPayment(quoteId: string): RequestPaymentCall;
}

export interface AgentTurn {
  body: string;
  toolCalls: ToolCall[];
  /** Hand the conversation to the vendor (NEEDS_ATTENTION). */
  escalate: boolean;
}

const PIDGIN = /\b(abeg|dey|wetin|una|oga|wan|abi|sha|na|don|sef|wahala|wey|o)\b/i;
const ESCALATE = /\b(exchange|refund|return|swap|too tight|too big|complain|damaged|spoil|late|not delivered|never reach)\b/i;
const BULK = /\b(wholesale|bulk|([3-9]|\d{2,})\s*pairs)\b/i;
const PRODUCT_WORD = /(loafer|sneaker|slipper|heel|slide|boot|sandal|mule)/i;
const OFFER_CUE = /\b(do am|do it|make (it|am)|last price|i fit pay|i go pay|i can pay|can you do|how about|abeg|\d+\s*k)\b/i;
const BUY_CUE = /\b(i('ll| will)? take|i want (it|am|one)|i wan buy|buy am|i go take|send (the )?link)\b/i;
const INQUIRY = /\b(how much|price|you get|do you have|have you got|available|in stock|wetin)\b/i;
const PAID_CLAIM = /\b(i (don|have|just) (pay|paid|sent|send|transfer)|paid|transferred|sent the money)\b/i;
const GREETING = /^\s*(hi|hello|hey|good (morning|afternoon|evening)|how far|bawo|kedu|sannu)\b/i;
const THANKS = /\b(thank|thanks|tanx|e se|daalu|nagode)\b/i;

function say(lang: Lang, en: string, pcm: string): string {
  return lang === "pcm" ? pcm : en;
}

function shortName(productId: string): string {
  return FAMILY_BY_PRODUCT_ID.get(productId) ?? "item";
}

function sizesInStock(hits: CatalogHit[]): string {
  const sizes = hits.filter((h) => h.stockOnHand > 0).map((h) => SIZE_BY_PRODUCT_ID.get(h.productId));
  if (sizes.length <= 1) return String(sizes[0] ?? "");
  return `${sizes.slice(0, -1).join(", ")} and ${sizes.at(-1)}`;
}

function requestedSize(text: string, memory: AgentMemory): number | undefined {
  const explicit = text.match(/size\s*(\d{2})/i)?.[1];
  if (explicit) return Number(explicit);
  const bare = text.match(/^\D*\b(\d{2})\b\D*$/)?.[1];
  if (bare && memory.family && !OFFER_CUE.test(text)) {
    const n = Number(bare);
    if (n >= 30 && n <= 48) return n;
  }
  return undefined;
}

export function respond(
  text: string,
  memory: AgentMemory,
  tools: AgentTools,
  customerName: string,
): AgentTurn {
  if (PIDGIN.test(text)) memory.lang = "pcm";
  else if (/\b(the|please|could|would|can you|is|are)\b/i.test(text)) memory.lang = "en";
  const lang = memory.lang;
  // Address real buyers by first name; the simulator's "Demo buyer" gets no name.
  const firstName = customerName === "Demo buyer" ? "" : (customerName.split(" ")[0] ?? "");
  const named = firstName ? `, ${firstName}` : "";
  const calls: ToolCall[] = [];
  const turn = (body: string, escalate = false): AgentTurn => ({ body, toolCalls: calls, escalate });

  // Complaints, exchanges and bulk orders go to the vendor.
  if (ESCALATE.test(text)) {
    return turn(
      say(
        lang,
        `Thanks for letting us know${named}. ${VENDOR_OWNER} handles this herself, so I've flagged it for her and she'll reply here shortly.`,
        `Thank you for telling us${named}. Na ${VENDOR_OWNER} dey handle this kind matter herself. I don call her attention, she go reply you here soon.`,
      ),
      true,
    );
  }

  if (BULK.test(text)) {
    return turn(
      say(
        lang,
        `Lovely! Bulk orders get a special price from ${VENDOR_OWNER} herself. I've let her know, and she'll reply here shortly.`,
        `Nice one! For bulk order, na ${VENDOR_OWNER} herself go give you special price. I don tell her, she go reply you here soon.`,
      ),
      true,
    );
  }

  // Never trust a "transfer alert": only the payment webhook confirms money.
  if (memory.awaitingPayment && PAID_CLAIM.test(text)) {
    return turn(
      say(
        lang,
        "Thank you! No need to send a screenshot. I'll confirm the moment Paystack tells us the payment has landed.",
        "Thank you! No need to send screenshot o. Once Paystack confirm say the money land, I go tell you sharp sharp.",
      ),
    );
  }

  const area = findDeliveryArea(text);
  if (area) memory.deliveryArea = area;

  const size = requestedSize(text, memory);
  const offer = OFFER_CUE.test(text) ? parseOfferKobo(text) : undefined;
  const wantsToBuy = memory.dealAgreed || BUY_CUE.test(text);

  // Size or product question: look it up.
  if ((INQUIRY.test(text) || size !== undefined) && offer === undefined && !(wantsToBuy && area)) {
    // "Na size 43" means the item we were already discussing.
    const query =
      !PRODUCT_WORD.test(text) && memory.family
        ? `${memory.family}${size !== undefined ? ` size ${size}` : ""}`
        : extractQuery(text);
    const search = tools.searchCatalog(query);
    calls.push(search);
    const hits = search.output.results;
    const first = hits[0];

    if (!first) {
      return turn(
        say(
          lang,
          "We don't have that one right now. We stock loafers, sneakers, palm slippers, heels, slides, Chelsea boots, mules and kids' sandals. Anything there catch your eye?",
          "We no get that one for now o. We get loafers, sneakers, palm slippers, heels, slides, Chelsea boots, mules and pikin sandals. Which one you like?",
        ),
      );
    }

    memory.family = FAMILY_BY_PRODUCT_ID.get(first.productId);
    const price = formatNaira(first.priceKobo);
    const greeting = GREETING.test(text) ? `${text.match(GREETING)?.[0]?.trim()}! ` : "";

    if (size !== undefined || hits.length === 1) {
      if (first.stockOnHand === 0) {
        const others = tools.searchCatalog(memory.family ?? first.name);
        calls.push(others);
        const left = sizesInStock(others.output.results);
        memory.productId = undefined;
        return turn(
          left
            ? say(
                lang,
                `${greeting}Sorry, size ${SIZE_BY_PRODUCT_ID.get(first.productId)} is sold out. We still have size ${left} at ${price}.`,
                `${greeting}Size ${SIZE_BY_PRODUCT_ID.get(first.productId)} don finish o. Na size ${left} remain, ${price}.`,
              )
            : say(lang, `${greeting}Sorry, that one is sold out.`, `${greeting}That one don finish o.`),
        );
      }
      memory.productId = first.productId;
      const pairs = first.stockOnHand === 1 ? "1 pair" : `${first.stockOnHand} pairs`;
      return turn(
        say(
          lang,
          `${greeting}Yes, the ${first.name.replace(", size", " in size")} are available at ${price}. Genuine leather, and we have ${pairs} left.`,
          `${greeting}${first.name} dey available, ${price}. Na original leather, ${pairs} remain.`,
        ),
      );
    }

    return turn(
      say(
        lang,
        `${greeting}The ${memory.family} are ${price}. We have size ${sizesInStock(hits)} in stock. Which size do you wear?`,
        `${greeting}${memory.family} na ${price}. Size ${sizesInStock(hits)} dey ground. Which size you dey wear?`,
      ),
    );
  }

  // Haggling.
  if (offer !== undefined) {
    if (!memory.family) {
      return turn(say(lang, "Which item would you like? Tell me and I'll check the price.", "Which one you want? Tell me make I check the price."));
    }
    const productId = memory.productId ?? tools.searchCatalog(memory.family).output.results.find((h) => h.stockOnHand > 0)?.productId;
    if (!productId) return turn(say(lang, "Sorry, that one is sold out.", "That one don finish o."));

    const evaluation = tools.evaluateOffer(productId, offer);
    calls.push(evaluation);
    const { decision, counterKobo, agreedPriceKobo } = evaluation.output;

    if (decision === "ACCEPT" && agreedPriceKobo !== undefined) {
      memory.dealAgreed = true;
      const item = memory.productId
        ? `the size ${SIZE_BY_PRODUCT_ID.get(memory.productId)} ${shortName(memory.productId).split(" ").at(-1)?.toLowerCase()}`
        : `the ${memory.family}`;
      const next = !memory.productId
        ? say(lang, "Which size, and where should we deliver?", "Which size, and where we go deliver am?")
        : say(lang, "Where should we deliver?", "Where we go deliver am?");
      if (memory.productId && memory.deliveryArea) return checkout(memory, tools, calls, lang);
      return turn(say(lang, `Deal! ${formatNaira(agreedPriceKobo)} for ${item}. ${next}`, `Deal! ${formatNaira(agreedPriceKobo)} for ${item}. ${next}`));
    }

    const counter = formatNaira(counterKobo ?? 0);
    const offered = formatNaira(offer);
    if (decision === "HOLD") {
      return turn(
        say(
          lang,
          `I hear you, but ${counter} is truly the last price on this one. It's genuine leather that will last you years.`,
          `I hear you, but ${counter} na the last last price for this one. Na original leather, e go last you well.`,
        ),
      );
    }
    return turn(
      say(
        lang,
        `${offered} is too low for this quality, I'm afraid. The best I can do is ${counter}.`,
        `Ah, ${offered} too small for this quality o. Best I fit do na ${counter}.`,
      ),
    );
  }

  // Ready to buy: need a size and an address before quoting.
  if (wantsToBuy && memory.family) {
    if (!memory.productId) {
      return turn(say(lang, "Great! Which size do you wear?", "Correct! Which size you dey wear?"));
    }
    if (!memory.deliveryArea) {
      return turn(say(lang, "Great! Where should we deliver?", "Correct! Where we go deliver am?"));
    }
    return checkout(memory, tools, calls, lang);
  }

  if (GREETING.test(text)) {
    return turn(
      say(
        lang,
        `Hello${named ? ` ${firstName}` : ""}, welcome to Ada's Footwear! What are you looking for today?`,
        `How far${named ? ` ${firstName}` : ""}! Welcome to Ada's Footwear. Wetin you dey find today?`,
      ),
    );
  }

  if (THANKS.test(text)) {
    return turn(say(lang, "You're welcome! Anything else I can help with?", "You're welcome! Anything else?"));
  }

  return turn(
    say(
      lang,
      `I'm not sure I can help with that, so I've asked ${VENDOR_OWNER} to take a look. She'll reply here shortly.`,
      `I no too sure about this one, so I don call ${VENDOR_OWNER}. She go reply you here soon.`,
    ),
    true,
  );
}

function checkout(memory: AgentMemory, tools: AgentTools, calls: ToolCall[], lang: Lang): AgentTurn {
  const productId = memory.productId as string;
  const area = memory.deliveryArea as string;
  const quote = tools.getQuote(productId, area);
  calls.push(quote);
  const payment = tools.requestPayment(quote.output.quoteId);
  calls.push(payment);
  memory.awaitingPayment = true;

  const fee = formatNaira(quote.output.deliveryFeeKobo);
  const total = formatNaira(quote.output.totalKobo);
  const link = payment.output.paymentUrl;
  return {
    toolCalls: calls,
    escalate: false,
    body: say(
      lang,
      `Delivery to ${area} is ${fee}, so your total is ${total}. Pay securely here: ${link}\nOnce Paystack confirms your payment, we'll pack your order straight away.`,
      `Delivery to ${area} na ${fee}, so your total na ${total}. Pay for here: ${link}\nOnce Paystack confirm your payment, we go pack your order sharp sharp.`,
    ),
  };
}
