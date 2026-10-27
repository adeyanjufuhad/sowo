import type { ToolCall } from "@sowo/shared";
import { describe, expect, it } from "vitest";
import { summarizeToolCall } from "./tool-calls";

const payment = (output: Partial<Extract<ToolCall, { tool: "request_payment" }>["output"]>): ToolCall => ({
  tool: "request_payment",
  input: { quoteId: "q_1" },
  output: { orderId: "o1", reference: "SW-ABC123", amountKobo: 4_350_000, ...output },
});

describe("summarizeToolCall", () => {
  it("describes a Paystack payment request", () => {
    const summary = summarizeToolCall(payment({ paymentUrl: "https://paystack.test/pay/SW-ABC123" }));
    expect(summary.server).toBe("order SW-ABC123 · Paystack link · ₦43,500");
  });

  it("describes a bank-transfer payment request without a link", () => {
    const summary = summarizeToolCall(
      payment({
        method: "MANUAL",
        bank: { bankName: "GTBank", accountName: "Ada Okafor", accountNumber: "0123456789" },
      }),
    );
    expect(summary.server).toBe("order SW-ABC123 · bank transfer to Ada · ₦43,500");
  });

  it("does not crash on a tool it does not know", () => {
    const unknown = { tool: "report_payment_sent", input: {}, output: {} } as unknown as ToolCall;
    expect(summarizeToolCall(unknown).tool).toBe("report_payment_sent");
  });
});
