import type { ListConversationsResponse } from "@sowo/shared";
import { handle } from "@/lib/mock/http";
import { listConversations } from "@/lib/mock/store";

export function GET() {
  return handle((state): ListConversationsResponse => ({ conversations: listConversations(state) }));
}
