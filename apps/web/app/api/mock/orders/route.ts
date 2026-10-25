import type { ListOrdersResponse } from "@sowo/shared";
import { handle } from "@/lib/mock/http";
import { listOrders } from "@/lib/mock/store";

export function GET() {
  return handle((state): ListOrdersResponse => ({ orders: listOrders(state) }));
}
