// Typed client for the Sowo API. Talks to the real backend when
// NEXT_PUBLIC_API_URL is set, otherwise to the built-in mock at /api/mock.

import {
  endpoints,
  type ApiError,
  type Endpoint,
  type RequestOf,
  type ResponseOf,
  type SimulatorMessageRequest,
  type SimulatorPaymentRequest,
} from "@sowo/shared";

const MOCK_BASE = "/api/mock";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || MOCK_BASE;
export const USING_MOCK = API_BASE === MOCK_BASE;

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<E extends Endpoint<unknown, unknown>>(
  endpoint: E,
  body?: RequestOf<E>,
): Promise<ResponseOf<E>> {
  const response = await fetch(`${API_BASE}${endpoint.path}`, {
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

export const api = {
  listConversations: () => call(endpoints.listConversations()),
  listMessages: (id: string) => call(endpoints.listMessages(id)),
  pauseConversation: (id: string) => call(endpoints.pauseConversation(id)),
  resumeConversation: (id: string) => call(endpoints.resumeConversation(id)),
  sendVendorReply: (id: string, body: string) => call(endpoints.sendVendorReply(id), { body }),
  listOrders: () => call(endpoints.listOrders()),
  listProducts: () => call(endpoints.listProducts()),
  sendSimulatorMessage: (request: SimulatorMessageRequest) =>
    call(endpoints.sendSimulatorMessage(), request),
  simulatePayment: (request: SimulatorPaymentRequest) => call(endpoints.simulatePayment(), request),
};
