// Typed client for the Sowo API.
// With NEXT_PUBLIC_API_URL set, it calls the real backend (apps/api) over HTTP.
// Without it, it runs the mock backend in the browser (lib/mock/local.ts), so the
// demo works offline and on serverless hosting. The same mock is also served over
// HTTP at /api/mock for curl and for comparing against the real backend.

import {
  endpoints,
  type ApiError,
  type Endpoint,
  type RequestOf,
  type ResponseOf,
  type SimulatorMessageRequest,
  type SimulatorPaymentRequest,
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

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "";

/** True when no backend is configured and the in-browser mock answers instead. */
export const USING_MOCK = !API_URL;

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

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiRequestError(response.status, payload?.error.message ?? `Request failed (${response.status})`);
  }
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
  sendSimulatorMessage: (request: SimulatorMessageRequest) => call(endpoints.sendSimulatorMessage(), request),
  simulatePayment: (request: SimulatorPaymentRequest) => call(endpoints.simulatePayment(), request),
};

export type SowoApi = typeof httpApi;

// A short pause on Sowo's replies so the typing indicator has a moment to show.
const REPLY_LATENCY_MS = 650;

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
};

export const api: SowoApi = USING_MOCK ? localApi : httpApi;

/** Reset the in-browser demo data. Does nothing against a real backend. */
export function resetDemoData() {
  if (USING_MOCK) resetLocalMock();
}
