import type { SimulatorPaymentRequest, SimulatorPaymentResponse } from "@sowo/shared";
import { handleWithBody } from "@/lib/mock/http";
import { MockError, settlePayment } from "@/lib/mock/store";

/** Stands in for the Paystack webhook so the demo can finish a sale offline. */
export function POST(request: Request) {
  return handleWithBody<SimulatorPaymentRequest, SimulatorPaymentResponse>(request, (state, body, now) => {
    if (body?.outcome !== "SUCCESS" && body?.outcome !== "FAILED") {
      throw new MockError(400, 'outcome must be "SUCCESS" or "FAILED"');
    }
    return settlePayment(state, String(body.reference ?? ""), body.outcome, now);
  });
}
