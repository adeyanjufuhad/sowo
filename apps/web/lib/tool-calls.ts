import { formatNaira, type ToolCall } from "@sowo/shared";

export interface ToolCallSummary {
  tool: string;
  /** What the model chose to do. */
  model: string;
  /** What the server computed. */
  server: string;
}

/** One-line, human readable view of a tool call for the replay. Never shows a floor price: there isn't one to show. */
export function summarizeToolCall(call: ToolCall): ToolCallSummary {
  switch (call.tool) {
    case "search_catalog": {
      const hits = call.output.results;
      const first = hits[0];
      return {
        tool: call.tool,
        model: `query: "${call.input.query}"`,
        server: first
          ? `${hits.length} match · ${formatNaira(first.priceKobo)} · ${first.stockOnHand} in stock`
          : "no matches",
      };
    }
    case "evaluate_offer": {
      const { decision, counterKobo, agreedPriceKobo } = call.output;
      return {
        tool: call.tool,
        model: `offer ${formatNaira(call.input.offerKobo)} on ${call.input.productId}`,
        server:
          decision === "ACCEPT"
            ? `ACCEPT at ${formatNaira(agreedPriceKobo ?? 0)}`
            : `${decision} at ${formatNaira(counterKobo ?? 0)}`,
      };
    }
    case "get_quote": {
      const q = call.output;
      const items = call.input.items.map((i) => `${i.quantity}× ${i.productId}`).join(", ");
      return {
        tool: call.tool,
        model: `${items} to ${call.input.deliveryArea}`,
        server: `${formatNaira(q.subtotalKobo)} + ${formatNaira(q.deliveryFeeKobo)} delivery = ${formatNaira(q.totalKobo)}`,
      };
    }
    case "request_payment":
      return {
        tool: call.tool,
        model: `pay quote ${call.input.quoteId}`,
        server: `order ${call.output.orderId.replace("ord_", "#")} · Paystack link · ${formatNaira(call.output.amountKobo)}`,
      };
  }
}
