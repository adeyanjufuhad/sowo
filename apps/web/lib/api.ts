// Typed client for the Sowo API.
// With NEXT_PUBLIC_API_URL set, it calls the real backend (apps/api) through this site's /api/proxy.
// Without it, it runs the mock backend in the browser (lib/mock/local.ts), so the
// demo works offline and on serverless hosting. The same mock is also served over
// HTTP at /api/mock for curl and for comparing against the real backend.

import {
  endpoints,
  type ApiError,
  type Endpoint,
  type DeliveryZoneInput,
  type LoginRequest,
  type ProductCreate,
  type ProductUpdate,
  type RequestOf,
  type ResponseOf,
  type SimulatorMessageRequest,
  type SimulatorPaymentRequest,
  type SignupRequest,
  type SimulatorReceiptRequest,
  type VendorSettingsUpdate,
} from "@sowo/shared";
import { ApiRequestError } from "./api-error";
import { resetLocalMock, runLocal } from "./mock/local";
import {
  listConversations,
  listMessages,
  listOrders,
  listProducts,
  pauseConversation,
  receiveBuyerMessage,
  resumeConversation,
  sendVendorReply,
  settlePayment,
} from "./mock/store";

export { ApiRequestError };

/** True when no backend is configured and the in-browser mock answers instead. */
export const USING_MOCK = !process.env.NEXT_PUBLIC_API_URL?.trim();

// With a backend, the browser talks to this site's own /api/proxy, which adds the vendor's session cookie and
// forwards to the API (see app/api/proxy). The API's address itself is only known to the server.
const API_URL = USING_MOCK ? "" : "/api/proxy";

async function call<E extends Endpoint<unknown, unknown>>(
  endpoint: E,
  body?: RequestOf<E>,
): Promise<ResponseOf<E>> {
  const response = await fetch(`${API_URL}${endpoint.path}`, {
    method: endpoint.method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  if (response.status === 401 && !endpoint.path.startsWith("/auth/") && typeof window !== "undefined") {
    // The session ended (or never existed): go and sign in, then come back here.
    const here = window.location.pathname + window.location.search;
    // A full navigation on purpose: it drops whatever the signed-out page was holding in memory.
    window.location.assign(new URL(`/login?next=${encodeURIComponent(here)}`, window.location.origin));
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiRequestError(response.status, payload?.error.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as ResponseOf<E>;
  return (await response.json()) as ResponseOf<E>;
}

const httpApi = {
  listConversations: () => call(endpoints.listConversations()),
  listMessages: (id: string) => call(endpoints.listMessages(id)),
  pauseConversation: (id: string) => call(endpoints.pauseConversation(id)),
  resumeConversation: (id: string) => call(endpoints.resumeConversation(id)),
  sendVendorReply: (id: string, body: string) => call(endpoints.sendVendorReply(id), { body }),
  listOrders: () => call(endpoints.listOrders()),
  listProducts: () => call(endpoints.listProducts()),
  createProduct: (request: ProductCreate) => call(endpoints.createProduct(), request),
  updateProduct: (id: string, request: ProductUpdate) => call(endpoints.updateProduct(id), request),
  deleteProduct: (id: string) => call(endpoints.deleteProduct(id)),
  listDeliveryZones: () => call(endpoints.listDeliveryZones()),
  createDeliveryZone: (request: DeliveryZoneInput) => call(endpoints.createDeliveryZone(), request),
  updateDeliveryZone: (id: string, request: Partial<DeliveryZoneInput>) =>
    call(endpoints.updateDeliveryZone(id), request),
  deleteDeliveryZone: (id: string) => call(endpoints.deleteDeliveryZone(id)),
  sendSimulatorMessage: (request: SimulatorMessageRequest) => call(endpoints.sendSimulatorMessage(), request),
  simulatePayment: (request: SimulatorPaymentRequest) => call(endpoints.simulatePayment(), request),
  sendSimulatorReceipt: (request: SimulatorReceiptRequest) => call(endpoints.sendSimulatorReceipt(), request),
  markOrderPaid: (id: string) => call(endpoints.markOrderPaid(id)),
  signup: (request: SignupRequest) => call(endpoints.signup(), request),
  login: (request: LoginRequest) => call(endpoints.login(), request),
  logout: () => call(endpoints.logout()),
  me: () => call(endpoints.me()),
  getVendorSettings: () => call(endpoints.getVendorSettings()),
  updateVendorSettings: (request: VendorSettingsUpdate) => call(endpoints.updateVendorSettings(), request),
};

export type SowoApi = typeof httpApi;

// A short pause on Sowo's replies so the typing indicator has a moment to show.
const REPLY_LATENCY_MS = 650;

// Bank-transfer mode confirms payments through the real backend; the offline demo only has Paystack-style checkout.
const needsBackend = () => Promise.reject(new ApiRequestError(409, "Bank transfers need the real backend. Set NEXT_PUBLIC_API_URL."));

const localApi: SowoApi = {
  listConversations: () => runLocal((s) => ({ conversations: listConversations(s) })),
  listMessages: (id) => runLocal((s) => listMessages(s, id)),
  pauseConversation: (id) => runLocal((s) => ({ conversation: pauseConversation(s, id) })),
  resumeConversation: (id) => runLocal((s) => ({ conversation: resumeConversation(s, id) })),
  sendVendorReply: (id, body) => runLocal((s, now) => sendVendorReply(s, id, body, now)),
  listOrders: () => runLocal((s) => ({ orders: listOrders(s) })),
  listProducts: () => runLocal((s) => ({ products: listProducts(s) })),
  sendSimulatorMessage: (request) =>
    runLocal(
      (s, now) =>
        receiveBuyerMessage(
          s,
          { conversationId: request.conversationId, customerName: request.customerName, platform: "SIMULATOR", body: request.body },
          now,
        ),
      REPLY_LATENCY_MS,
    ),
  simulatePayment: (request) =>
    runLocal((s, now) => settlePayment(s, request.reference, request.outcome, now), REPLY_LATENCY_MS),
  sendSimulatorReceipt: needsBackend,
  markOrderPaid: needsBackend,
  signup: needsBackend,
  login: needsBackend,
  logout: needsBackend,
  me: needsBackend,
  getVendorSettings: needsBackend,
  updateVendorSettings: needsBackend,
  createProduct: needsBackend,
  updateProduct: needsBackend,
  deleteProduct: needsBackend,
  listDeliveryZones: needsBackend,
  createDeliveryZone: needsBackend,
  updateDeliveryZone: needsBackend,
  deleteDeliveryZone: needsBackend,
};

export const api: SowoApi = USING_MOCK ? localApi : httpApi;

/** Reset the in-browser demo data. Does nothing against a real backend. */
export function resetDemoData() {
  if (USING_MOCK) resetLocalMock();
}
