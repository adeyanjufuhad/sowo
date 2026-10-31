import { describe, expect, it } from "vitest";
import { productImageSrc } from "./product-image";

describe("productImageSrc", () => {
  it("loads uploaded pictures through this site's proxy", () => {
    expect(productImageSrc("/product-images/0b1c2d3e-0000-4000-8000-000000000000")).toBe(
      "/api/proxy/product-images/0b1c2d3e-0000-4000-8000-000000000000",
    );
  });

  it("leaves web addresses and the demo's own pictures alone", () => {
    expect(productImageSrc("https://example.com/tote.jpg")).toBe("https://example.com/tote.jpg");
    expect(productImageSrc("/products/loafer.svg")).toBe("/products/loafer.svg");
  });

  it("has nothing to show for an empty picture", () => {
    for (const value of ["", "  ", null, undefined]) expect(productImageSrc(value)).toBeNull();
  });
});
