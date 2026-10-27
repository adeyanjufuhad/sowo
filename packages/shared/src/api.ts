/**
 * Sowo API contract, shared by apps/web and apps/api.
 *
 * Rules that hold across every endpoint:
 * - All money is an integer number of kobo (₦1 = 100 kobo). Never floats, never naira.
 * - All timestamps are ISO 8601 strings in UTC, e.g. "2026-10-25T19:42:00.000Z".
 * - The model only phrases replies and picks tools. The server decides every price,
 *   total and stock change, so tool `output` is always computed by the server.
 * - A product's floor price is visible to the vendor only. It never appears in a
 *   tool input/output, a buyer-facing message, or anything the model sees.
 *
 * The prose version of this file, with examples, is docs/api-contract.md.
 */

/* -------------------------------------------------------------------------- */
/* Domain                                                                     */
/* -------------------------------------------------------------------------- */

export type Kobo = number;
export type IsoDateString = string;

export const CONVERSATION_STATUSES = [
  "AI_ACTIVE",
  "NEEDS_ATTENTION",
  "HUMAN_TAKEOVER",
  "CLOSED",
] as const;
export type ConversationStatus = (typeof CONVERSATION_STATUSES)[number];

/** Where the buyer is talking from. SIMULATOR is the /try page. */
export type Platform = "WHATSAPP" | "SIMULATOR";

export interface Conversation {
  id: string;
  customerName: string;
  platform: Platform;
  status: ConversationStatus;
  lastMessageAt: IsoDateString;
  /** Short text of the latest message, for the chats list. */
  preview: string;
}

export type MessageSender = "BUYER" | "AI" | "VENDOR";

export interface Message {
  id: string;
  conversationId: string;
  sender: MessageSender;
  body: string;
  createdAt: IsoDateString;
  /** Present on AI messages that used tools, in the order they ran. */
  toolCalls?: ToolCall[];
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  basePriceKobo: Kobo;
  /** Lowest price the vendor will accept. Vendor-only. */
  floorPriceKobo: Kobo;
  stockOnHand: number;
  imageUrl: string;
}

export const PAYMENT_STATUSES = ["PENDING", "PAID", "FAILED", "REFUNDED"] as const;
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];

export const FULFILLMENT_STATUSES = [
  "UNFULFILLED",
  "PACKAGING",
  "SHIPPED",
  "DELIVERED",
] as const;
export type FulfillmentStatus = (typeof FULFILLMENT_STATUSES)[number];

export interface OrderItem {
  productId: string;
  sku: string;
  name: string;
  quantity: number;
  /** Agreed price per unit after haggling. */
  unitPriceKobo: Kobo;
}

/** PAYSTACK: a checkout link, confirmed by Paystack. MANUAL: a bank transfer to the vendor, confirmed by the vendor. */
export type PaymentMethod = "PAYSTACK" | "MANUAL";

/** The vendor's own account, shown to the buyer for a bank-transfer order. */
export interface BankDetails {
  bankName: string;
  accountName: string;
  accountNumber: string;
}

export interface Order {
  id: string;
  customerName: string;
  items: OrderItem[];
  deliveryFeeKobo: Kobo;
  /** Sum of item lines plus delivery. */
  totalKobo: Kobo;
  paymentStatus: PaymentStatus;
  fulfillmentStatus: FulfillmentStatus;
  createdAt: IsoDateString;
  /** Optional extras the dashboard shows when present. */
  conversationId?: string;
  deliveryArea?: string;
  paymentReference?: string;
  /** Defaults to PAYSTACK when absent. */
  paymentMethod?: PaymentMethod;
  /** Bank transfer only: when the buyer said they had paid. Payment stays PENDING until the vendor confirms. */
  receiptReportedAt?: IsoDateString;
}

/* -------------------------------------------------------------------------- */
/* Tool calls                                                                 */
/* -------------------------------------------------------------------------- */
/* `input` is what the model chose. `output` is what the server computed.      */

export const TOOL_NAMES = [
  "search_catalog",
  "evaluate_offer",
  "get_quote",
  "request_payment",
] as const;
export type ToolName = (typeof TOOL_NAMES)[number];

export interface CatalogHit {
  productId: string;
  sku: string;
  name: string;
  priceKobo: Kobo;
  stockOnHand: number;
}

export interface SearchCatalogCall {
  tool: "search_catalog";
  input: { query: string };
  output: { results: CatalogHit[] };
}

/**
 * ACCEPT: offer is at or above the floor; agreedPriceKobo is set.
 * COUNTER: offer is below the floor; counterKobo is the server's next price.
 * HOLD: offer is below the floor and the server has no more room; counterKobo is the final price.
 * REJECT: offer is unrealistically low; no price is returned.
 * HANDOFF: repeated offers below the floor; the chat goes to the vendor, no price is returned.
 */
export type OfferDecision = "ACCEPT" | "COUNTER" | "HOLD" | "REJECT" | "HANDOFF";

export interface EvaluateOfferCall {
  tool: "evaluate_offer";
  /** `sku` is optional: it is the readable form of productId, for display. */
  input: { productId: string; offerKobo: Kobo; sku?: string };
  output: {
    decision: OfferDecision;
    agreedPriceKobo?: Kobo;
    counterKobo?: Kobo;
  };
}

export interface QuoteLine {
  productId: string;
  name: string;
  quantity: number;
  unitPriceKobo: Kobo;
  lineTotalKobo: Kobo;
}

export interface Quote {
  quoteId: string;
  lines: QuoteLine[];
  subtotalKobo: Kobo;
  deliveryArea: string;
  deliveryFeeKobo: Kobo;
  totalKobo: Kobo;
}

export interface GetQuoteCall {
  tool: "get_quote";
  /** No prices in the input: the server applies the agreed price itself. */
  input: { items: { productId: string; quantity: number; sku?: string }[]; deliveryArea: string };
  output: Quote;
}

export interface RequestPaymentCall {
  tool: "request_payment";
  input: { quoteId: string };
  output: {
    orderId: string;
    reference: string;
    amountKobo: Kobo;
    /** Paystack (test mode) checkout link. Absent for bank transfers. */
    paymentUrl?: string;
    /** Absent means PAYSTACK. */
    method?: PaymentMethod;
    /** Bank transfers: the vendor's account the buyer pays into. */
    bank?: BankDetails;
  };
}

export type ToolCall =
  | SearchCatalogCall
  | EvaluateOfferCall
  | GetQuoteCall
  | RequestPaymentCall;

/* -------------------------------------------------------------------------- */
/* Requests and responses                                                     */
/* -------------------------------------------------------------------------- */

export interface ListConversationsResponse {
  conversations: Conversation[];
}

export interface ListMessagesResponse {
  conversation: Conversation;
  messages: Message[];
}

/** Returned by pause and resume. */
export interface ConversationResponse {
  conversation: Conversation;
}

export interface VendorReplyRequest {
  body: string;
}

export interface VendorReplyResponse {
  conversation: Conversation;
  message: Message;
}

export interface ListOrdersResponse {
  orders: Order[];
}

export interface ListProductsResponse {
  products: Product[];
}

export interface SimulatorMessageRequest {
  /** Omit to start a new simulator conversation. */
  conversationId?: string;
  /** Used when starting a new conversation. Defaults to "Demo buyer". */
  customerName?: string;
  body: string;
}

export interface SimulatorMessageResponse {
  conversation: Conversation;
  /** The buyer's message first, then any AI replies, oldest first. */
  messages: Message[];
}

export interface SimulatorPaymentRequest {
  reference: string;
  outcome: "SUCCESS" | "FAILED";
}

export interface SimulatorPaymentResponse {
  order: Order;
  /** Messages the payment produced, e.g. the receipt. */
  messages: Message[];
}

export interface SimulatorReceiptRequest {
  reference: string;
}

export interface SimulatorReceiptResponse {
  order: Order;
  /** The buyer's "I've sent it" message and Sowo's reply. */
  messages: Message[];
}

export interface MarkPaidResponse {
  order: Order;
  /** The receipt sent to the buyer. Absent when the order was already paid. */
  message?: Message;
}

/* Accounts. The web app's server keeps the session token in an httpOnly cookie, so the browser sees only the vendor. */

export interface AuthVendor {
  id: string;
  name: string;
  email?: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  businessName: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SessionResponse {
  vendor: AuthVendor;
}

export interface ApiError {
  error: {
    code: "BAD_REQUEST" | "UNAUTHORIZED" | "NOT_FOUND" | "CONFLICT" | "INTERNAL";
    message: string;
  };
}

/* -------------------------------------------------------------------------- */
/* Endpoints                                                                  */
/* -------------------------------------------------------------------------- */

type Method = "GET" | "POST";

interface Endpoint<Req, Res> {
  method: Method;
  path: string;
  /** Phantom fields so callers can infer request and response types. */
  _req?: Req;
  _res?: Res;
}

function endpoint<Req, Res>(method: Method, path: string): Endpoint<Req, Res> {
  return { method, path };
}

const enc = encodeURIComponent;

/** Every endpoint, relative to the API base URL. */
export const endpoints = {
  listConversations: () =>
    endpoint<void, ListConversationsResponse>("GET", "/conversations"),
  listMessages: (id: string) =>
    endpoint<void, ListMessagesResponse>("GET", `/conversations/${enc(id)}/messages`),
  pauseConversation: (id: string) =>
    endpoint<void, ConversationResponse>("POST", `/conversations/${enc(id)}/pause`),
  resumeConversation: (id: string) =>
    endpoint<void, ConversationResponse>("POST", `/conversations/${enc(id)}/resume`),
  sendVendorReply: (id: string) =>
    endpoint<VendorReplyRequest, VendorReplyResponse>(
      "POST",
      `/conversations/${enc(id)}/messages`,
    ),
  listOrders: () => endpoint<void, ListOrdersResponse>("GET", "/orders"),
  listProducts: () => endpoint<void, ListProductsResponse>("GET", "/products"),
  sendSimulatorMessage: () =>
    endpoint<SimulatorMessageRequest, SimulatorMessageResponse>(
      "POST",
      "/simulator/messages",
    ),
  /** Demo helper: stands in for the Paystack webhook so the simulator works offline. */
  simulatePayment: () =>
    endpoint<SimulatorPaymentRequest, SimulatorPaymentResponse>(
      "POST",
      "/simulator/payments",
    ),
  signup: () => endpoint<SignupRequest, SessionResponse>("POST", "/auth/signup"),
  login: () => endpoint<LoginRequest, SessionResponse>("POST", "/auth/login"),
  logout: () => endpoint<void, { ok: boolean }>("POST", "/auth/logout"),
  me: () => endpoint<void, SessionResponse>("GET", "/auth/me"),
  /** Bank-transfer mode: the simulator buyer says they have sent the money. */
  sendSimulatorReceipt: () =>
    endpoint<SimulatorReceiptRequest, SimulatorReceiptResponse>(
      "POST",
      "/simulator/receipts",
    ),
  /** Bank-transfer mode: the vendor confirms the money reached their account. */
  markOrderPaid: (id: string) =>
    endpoint<void, MarkPaidResponse>("POST", `/orders/${enc(id)}/mark-paid`),
} as const;

export type RequestOf<E> = E extends Endpoint<infer Req, unknown> ? Req : never;
export type ResponseOf<E> = E extends Endpoint<unknown, infer Res> ? Res : never;
export type { Endpoint };
