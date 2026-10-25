import type { ConversationResponse } from "@sowo/shared";
import { handle } from "@/lib/mock/http";
import { resumeConversation } from "@/lib/mock/store";

export async function POST(_request: Request, ctx: RouteContext<"/api/mock/conversations/[id]/resume">) {
  const { id } = await ctx.params;
  return handle((state): ConversationResponse => ({ conversation: resumeConversation(state, id) }));
}
