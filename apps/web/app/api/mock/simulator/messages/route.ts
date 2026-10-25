import type { SimulatorMessageRequest, SimulatorMessageResponse } from "@sowo/shared";
import { handleWithBody } from "@/lib/mock/http";
import { receiveBuyerMessage } from "@/lib/mock/store";

/** Send a message as a buyer and get Sowo's reply, tool calls included. */
export function POST(request: Request) {
  return handleWithBody<SimulatorMessageRequest, SimulatorMessageResponse>(request, (state, body, now) =>
    receiveBuyerMessage(
      state,
      {
        conversationId: body?.conversationId,
        customerName: body?.customerName,
        platform: "SIMULATOR",
        body: String(body?.body ?? ""),
      },
      now,
    ),
  );
}
