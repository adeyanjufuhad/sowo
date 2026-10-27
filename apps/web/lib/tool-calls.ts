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
      const price = decision === "ACCEPT" ? agreedPriceKobo : counterKobo;
      return {
        tool: call.tool,
        model: `offer ${formatNaira(call.input.offerKobo)} on ${call.input.sku ?? call.input.productId}`,
        // REJECT and HANDOFF carry no price, so show just the decision.
        server: price === undefined ? decision : `${decision} at ${formatNaira(price)}`,
      };
    }
    case "get_quote": {
      const q = call.output;
      const items = call.input.items.map((i) => `${i.quantity}× ${i.sku ?? i.productId}`).join(", ");
      return {
        tool: call.tool,
        model: `${items} to ${call.input.deliveryArea}`,
        server: `${formatNaira(q.subtotalKobo)} + ${formatNaira(q.deliveryFeeKobo)} delivery = ${formatNaira(q.totalKobo)}`,
      };
    }
    case "request_payment": {
      const how = call.output.method === "MANUAL" ? "bank transfer to Ada" : "Paystack link";
      return {
        tool: call.tool,
        model: `pay quote ${call.input.quoteId}`,
        // The reference (SW-…) reads well; the order id may be a database UUID.
        server: `order ${call.output.reference} · ${how} · ${formatNaira(call.output.amountKobo)}`,
      };
    }
    default:
      // A tool this build doesn't know yet (the backend may be newer): show it plainly rather than crash.
      return { tool: (call as { tool: string }).tool, model: "", server: "" };
  }
}
