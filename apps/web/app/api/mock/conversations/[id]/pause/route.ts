import type { ConversationResponse } from "@sowo/shared";
import { handle } from "@/lib/mock/http";
import { pauseConversation } from "@/lib/mock/store";

export async function POST(_request: Request, ctx: RouteContext<"/api/mock/conversations/[id]/pause">) {
  const { id } = await ctx.params;
  return handle((state): ConversationResponse => ({ conversation: pauseConversation(state, id) }));
}
