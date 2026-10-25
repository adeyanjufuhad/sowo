import type { ListMessagesResponse, VendorReplyRequest, VendorReplyResponse } from "@sowo/shared";
import { handle, handleWithBody } from "@/lib/mock/http";
import { listMessages, sendVendorReply } from "@/lib/mock/store";

export async function GET(_request: Request, ctx: RouteContext<"/api/mock/conversations/[id]/messages">) {
  const { id } = await ctx.params;
  return handle((state): ListMessagesResponse => listMessages(state, id));
}

/** Vendor reply from the dashboard. */
export async function POST(request: Request, ctx: RouteContext<"/api/mock/conversations/[id]/messages">) {
  const { id } = await ctx.params;
  return handleWithBody<VendorReplyRequest, VendorReplyResponse>(request, (state, body, now) =>
    sendVendorReply(state, id, String(body?.body ?? ""), now),
  );
}
