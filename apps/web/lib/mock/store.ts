// In-memory mock of the Sowo backend. Holds state and implements the server side
// of every tool: prices, totals and stock are decided here, never in agent.ts.

import type {
  Conversation,
  Message,
  MessageSender,
  Order,
  Platform,
  Product,
  Quote,
  ToolCall,
} from "@sowo/shared";
import { formatNaira } from "@sowo/shared";
import { respond, freshMemory, type AgentMemory, type AgentTools } from "./agent";
import { FAMILY_BY_PRODUCT_ID, VENDOR_OWNER, searchCatalog, seedProducts } from "./catalog";
import { DELIVERY_FEES, NO_OFFERS_YET, evaluateOffer, type OfferHistory } from "./negotiation";

/** Server-side negotiation state. The agent never sees these numbers directly. */
interface Deal {
  family?: string;
  offers: OfferHistory;
  agreedPriceKobo?: number;
}

export interface MockState {
  products: Product[];
  conversations: Conversation[];
  messages: Message[];
  orders: Order[];
  memory: Map<string, AgentMemory>;
  deals: Map<string, Deal>;
  quotes: Map<string, { quote: Quote; conversationId: string }>;
  seq: number;
}

export class MockError extends Error {
  constructor(
    readonly status: 400 | 404 | 409,
    message: string,
  ) {
    super(message);
  }
}

const REPLY_DELAY_MS = 2_000;

export function createEmptyState(): MockState {
  return {
    products: seedProducts(),
    conversations: [],
    messages: [],
    orders: [],
    memory: new Map(),
    deals: new Map(),
    quotes: new Map(),
    seq: 1000,
  };
}

function nextId(state: MockState, prefix: string): string {
  state.seq += 1;
  return `${prefix}_${state.seq.toString(36)}`;
}

function getConversation(state: MockState, id: string): Conversation {
  const conversation = state.conversations.find((c) => c.id === id);
  if (!conversation) throw new MockError(404, `Conversation ${id} not found`);
  return conversation;
}

function getProduct(state: MockState, id: string): Product {
  const product = state.products.find((p) => p.id === id);
  if (!product) throw new MockError(404, `Product ${id} not found`);
  return product;
}

function addMessage(
  state: MockState,
  conversation: Conversation,
  sender: MessageSender,
  body: string,
  at: Date,
  toolCalls?: ToolCall[],
): Message {
  const message: Message = {
    id: nextId(state, "msg"),
    conversationId: conversation.id,
    sender,
    body,
    createdAt: at.toISOString(),
    ...(toolCalls?.length ? { toolCalls } : {}),
  };
  state.messages.push(message);
  conversation.lastMessageAt = message.createdAt;
  conversation.preview = body.split("\n")[0] ?? body;
  return message;
}

/* ---------------------------------- reads --------------------------------- */

export function listConversations(state: MockState): Conversation[] {
  return [...state.conversations].sort((a, b) => b.lastMessageAt.localeCompare(a.lastMessageAt));
}

export function listMessages(state: MockState, conversationId: string) {
  const conversation = getConversation(state, conversationId);
  const messages = state.messages
    .filter((m) => m.conversationId === conversationId)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return { conversation, messages };
}

export function listOrders(state: MockState): Order[] {
  return [...state.orders].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function listProducts(state: MockState): Product[] {
  return state.products;
}

/* ------------------------------ vendor actions ----------------------------- */

export function pauseConversation(state: MockState, id: string): Conversation {
  const conversation = getConversation(state, id);
  conversation.status = "HUMAN_TAKEOVER";
  return conversation;
}

export function resumeConversation(state: MockState, id: string): Conversation {
  const conversation = getConversation(state, id);
  conversation.status = "AI_ACTIVE";
  return conversation;
}

export function sendVendorReply(state: MockState, id: string, body: string, now: Date) {
  const text = body.trim();
  if (!text) throw new MockError(400, "Reply body is empty");
  const conversation = getConversation(state, id);
  conversation.status = "HUMAN_TAKEOVER";
  const message = addMessage(state, conversation, "VENDOR", text, now);
  return { conversation, message };
}

/* ------------------------------- server tools ------------------------------ */

function toolsFor(state: MockState, conversation: Conversation): AgentTools {
  const deal = state.deals.get(conversation.id) ?? { offers: NO_OFFERS_YET };
  state.deals.set(conversation.id, deal);

  return {
    searchCatalog(query) {
      return { tool: "search_catalog", input: { query }, output: { results: searchCatalog(state.products, query) } };
    },

    evaluateOffer(productId, offerKobo) {
      const product = getProduct(state, productId);
      const family = FAMILY_BY_PRODUCT_ID.get(productId);
      if (deal.family !== family) {
        deal.family = family;
        deal.offers = NO_OFFERS_YET;
        deal.agreedPriceKobo = undefined;
      }
      const result = evaluateOffer(product, offerKobo, deal.offers);
      deal.offers = result.history;
      if (result.output.decision === "ACCEPT") deal.agreedPriceKobo = result.output.agreedPriceKobo;
      return { tool: "evaluate_offer", input: { productId, offerKobo }, output: result.output };
    },

    getQuote(productId, deliveryArea) {
      const product = getProduct(state, productId);
      const sameDeal = deal.family === FAMILY_BY_PRODUCT_ID.get(productId);
      const unitPriceKobo = sameDeal && deal.agreedPriceKobo !== undefined ? deal.agreedPriceKobo : product.basePriceKobo;
      const deliveryFeeKobo = DELIVERY_FEES[deliveryArea];
      if (deliveryFeeKobo === undefined) throw new MockError(400, `No delivery to ${deliveryArea}`);

      const quote: Quote = {
        quoteId: nextId(state, "q"),
        lines: [{ productId, name: product.name, quantity: 1, unitPriceKobo, lineTotalKobo: unitPriceKobo }],
        subtotalKobo: unitPriceKobo,
        deliveryArea,
        deliveryFeeKobo,
        totalKobo: unitPriceKobo + deliveryFeeKobo,
      };
      state.quotes.set(quote.quoteId, { quote, conversationId: conversation.id });
      return {
        tool: "get_quote",
        input: { items: [{ productId, quantity: 1 }], deliveryArea },
        output: quote,
      };
    },

    requestPayment(quoteId) {
      const entry = state.quotes.get(quoteId);
      if (!entry) throw new MockError(404, `Quote ${quoteId} not found`);
      const { quote } = entry;

      const items = quote.lines.map((line) => {
        const product = getProduct(state, line.productId);
        if (product.stockOnHand < line.quantity) throw new MockError(409, `${product.name} is out of stock`);
        product.stockOnHand -= line.quantity; // reserved until payment settles
        return { productId: product.id, sku: product.sku, name: product.name, quantity: line.quantity, unitPriceKobo: line.unitPriceKobo };
      });

      const orderNumber = 1040 + state.orders.length + 1;
      const reference = `SW-${orderNumber}-${state.seq.toString(36).toUpperCase()}`;
      const order: Order = {
        id: `ord_${orderNumber}`,
        customerName: conversation.customerName,
        items,
        deliveryFeeKobo: quote.deliveryFeeKobo,
        totalKobo: quote.totalKobo,
        paymentStatus: "PENDING",
        fulfillmentStatus: "UNFULFILLED",
        createdAt: conversation.lastMessageAt,
        conversationId: conversation.id,
        deliveryArea: quote.deliveryArea,
        paymentReference: reference,
      };
      state.orders.push(order);
      return {
        tool: "request_payment",
        input: { quoteId },
        output: {
          orderId: order.id,
          reference,
          amountKobo: order.totalKobo,
          // Reserved .test domain: obviously not a real checkout.
          paymentUrl: `https://paystack.test/pay/${reference}`,
        },
      };
    },
  };
}

/* --------------------------------- buyers --------------------------------- */

export function receiveBuyerMessage(
  state: MockState,
  input: { conversationId?: string; customerName?: string; platform: Platform; body: string },
  now: Date,
) {
  const body = input.body.trim();
  if (!body) throw new MockError(400, "Message body is empty");

  let conversation: Conversation;
  if (input.conversationId) {
    conversation = getConversation(state, input.conversationId);
  } else {
    conversation = {
      id: nextId(state, "conv"),
      customerName: input.customerName?.trim() || "Demo buyer",
      platform: input.platform,
      status: "AI_ACTIVE",
      lastMessageAt: now.toISOString(),
      preview: body,
    };
    state.conversations.push(conversation);
  }

  if (conversation.status === "CLOSED") {
    conversation.status = "AI_ACTIVE";
    state.memory.set(conversation.id, { ...freshMemory(), lang: state.memory.get(conversation.id)?.lang ?? "en" });
    state.deals.delete(conversation.id);
  }

  const messages = [addMessage(state, conversation, "BUYER", body, now)];
  if (conversation.status !== "AI_ACTIVE") return { conversation, messages };

  const memory = state.memory.get(conversation.id) ?? freshMemory();
  state.memory.set(conversation.id, memory);
  const reply = respond(body, memory, toolsFor(state, conversation), conversation.customerName);
  const replyAt = new Date(now.getTime() + REPLY_DELAY_MS);
  messages.push(addMessage(state, conversation, "AI", reply.body, replyAt, reply.toolCalls));
  if (reply.escalate) conversation.status = "NEEDS_ATTENTION";

  return { conversation, messages };
}

/** Stands in for the Paystack webhook. */
export function settlePayment(
  state: MockState,
  reference: string,
  outcome: "SUCCESS" | "FAILED",
  now: Date,
) {
  const order = state.orders.find((o) => o.paymentReference === reference);
  if (!order) throw new MockError(404, `Payment ${reference} not found`);
  if (order.paymentStatus !== "PENDING") throw new MockError(409, `Order ${order.id} is already ${order.paymentStatus}`);

  const conversation = getConversation(state, order.conversationId ?? "");
  const memory = state.memory.get(conversation.id) ?? freshMemory();
  const pcm = memory.lang === "pcm";
  const item = order.items.map((i) => i.name).join(", ");
  memory.awaitingPayment = false;

  let body: string;
  if (outcome === "SUCCESS") {
    order.paymentStatus = "PAID";
    order.fulfillmentStatus = "PACKAGING";
    conversation.status = "CLOSED";
    body = pcm
      ? `Payment confirm ✅ We don receive ${formatNaira(order.totalKobo)} for order ${order.id.replace("ord_", "#")}.\nReceipt: ${reference}\n${VENDOR_OWNER} don dey pack your ${item}. E go reach ${order.deliveryArea} in 1 to 2 days. Thank you!`
      : `Payment confirmed ✅ We've received ${formatNaira(order.totalKobo)} for order ${order.id.replace("ord_", "#")}.\nReceipt: ${reference}\n${VENDOR_OWNER} is packing your ${item} now. Delivery to ${order.deliveryArea} takes 1 to 2 days. Thank you!`;
  } else {
    order.paymentStatus = "FAILED";
    for (const line of order.items) {
      const product = state.products.find((p) => p.id === line.productId);
      if (product) product.stockOnHand += line.quantity; // release the reservation
    }
    body = pcm
      ? "The payment no go through o. No money comot from your account. You wan try again?"
      : "That payment didn't go through, and nothing was charged. Would you like to try again?";
  }

  const messages = [addMessage(state, conversation, "AI", body, now)];
  return { order, messages };
}
