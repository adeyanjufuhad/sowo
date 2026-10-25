import type { ListProductsResponse } from "@sowo/shared";
import { handle } from "@/lib/mock/http";
import { listProducts } from "@/lib/mock/store";

export function GET() {
  return handle((state): ListProductsResponse => ({ products: listProducts(state) }));
}
