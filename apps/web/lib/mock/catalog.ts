// Ada's Footwear: the seeded vendor catalogue. One product per size, so stock is per size.

import type { CatalogHit, Product } from "@sowo/shared";

export const VENDOR_NAME = "Ada's Footwear";
export const VENDOR_OWNER = "Ada";

interface ProductSeed {
  id: string;
  sku: string;
  family: string;
  size: number;
  priceNaira: number;
  floorNaira: number;
  stock: number;
  image: string;
}

const SEEDS: ProductSeed[] = [
  { id: "prod_loafer_blk_42", sku: "LOAF-BLK-42", family: "Black Leather Loafers", size: 42, priceNaira: 45_000, floorNaira: 40_000, stock: 2, image: "loafer" },
  { id: "prod_loafer_blk_43", sku: "LOAF-BLK-43", family: "Black Leather Loafers", size: 43, priceNaira: 45_000, floorNaira: 40_000, stock: 3, image: "loafer" },
  { id: "prod_loafer_blk_44", sku: "LOAF-BLK-44", family: "Black Leather Loafers", size: 44, priceNaira: 45_000, floorNaira: 40_000, stock: 1, image: "loafer" },
  { id: "prod_loafer_brn_43", sku: "LOAF-BRN-43", family: "Brown Suede Loafers", size: 43, priceNaira: 42_000, floorNaira: 37_000, stock: 4, image: "loafer" },
  { id: "prod_sneaker_wht_41", sku: "SNKR-WHT-41", family: "White Leather Sneakers", size: 41, priceNaira: 38_000, floorNaira: 33_000, stock: 5, image: "sneaker" },
  { id: "prod_sneaker_wht_44", sku: "SNKR-WHT-44", family: "White Leather Sneakers", size: 44, priceNaira: 38_000, floorNaira: 33_000, stock: 0, image: "sneaker" },
  { id: "prod_palm_tan_43", sku: "PALM-TAN-43", family: "Tan Palm Slippers", size: 43, priceNaira: 18_000, floorNaira: 15_000, stock: 8, image: "slipper" },
  { id: "prod_palm_blk_42", sku: "PALM-BLK-42", family: "Black Palm Slippers", size: 42, priceNaira: 18_000, floorNaira: 15_000, stock: 6, image: "slipper" },
  { id: "prod_heel_ankara_39", sku: "HEEL-ANK-39", family: "Ankara Block Heels", size: 39, priceNaira: 28_000, floorNaira: 24_000, stock: 3, image: "heel" },
  { id: "prod_heel_nude_38", sku: "HEEL-NUD-38", family: "Nude Pointed Heels", size: 38, priceNaira: 32_000, floorNaira: 27_500, stock: 2, image: "heel" },
  { id: "prod_slide_asooke_40", sku: "SLID-ASO-40", family: "Beaded Aso-Oke Slides", size: 40, priceNaira: 22_000, floorNaira: 18_500, stock: 4, image: "slide" },
  { id: "prod_boot_brn_43", sku: "BOOT-BRN-43", family: "Brown Chelsea Boots", size: 43, priceNaira: 55_000, floorNaira: 48_000, stock: 2, image: "boot" },
  { id: "prod_boot_blk_44", sku: "BOOT-BLK-44", family: "Black Chelsea Boots", size: 44, priceNaira: 55_000, floorNaira: 48_000, stock: 1, image: "boot" },
  { id: "prod_sandal_kids_32", sku: "SAND-KID-32", family: "Kids' School Sandals", size: 32, priceNaira: 9_500, floorNaira: 8_000, stock: 10, image: "sandal" },
  { id: "prod_mule_tan_39", sku: "MULE-TAN-39", family: "Tan Leather Mules", size: 39, priceNaira: 26_000, floorNaira: 22_000, stock: 3, image: "mule" },
];

export const FAMILY_BY_PRODUCT_ID = new Map(SEEDS.map((s) => [s.id, s.family]));
export const SIZE_BY_PRODUCT_ID = new Map(SEEDS.map((s) => [s.id, s.size]));

export function seedProducts(): Product[] {
  return SEEDS.map((s) => ({
    id: s.id,
    sku: s.sku,
    name: `${s.family}, size ${s.size}`,
    basePriceKobo: s.priceNaira * 100,
    floorPriceKobo: s.floorNaira * 100,
    stockOnHand: s.stock,
    imageUrl: `/products/${s.image}.svg`,
  }));
}

function stem(word: string): string {
  return word.length > 3 && word.endsWith("s") ? word.slice(0, -1) : word;
}

function tokens(text: string): string[] {
  return text.toLowerCase().match(/[a-z0-9]+/g)?.map(stem) ?? [];
}

/**
 * Keyword search over product names. A size in the query must match exactly.
 * Never returns floor prices: CatalogHit has no field for one.
 */
export function searchCatalog(products: Product[], query: string): CatalogHit[] {
  const queryTokens = new Set(tokens(query));
  const size = query.match(/size\s*(\d{2})/i)?.[1];

  return products
    .map((product) => {
      const nameTokens = tokens(product.name).filter((t) => !/^\d+$/.test(t) && t !== "size");
      const score = nameTokens.filter((t) => queryTokens.has(t)).length;
      return { product, score };
    })
    .filter(({ product, score }) => {
      if (score === 0) return false;
      return !size || SIZE_BY_PRODUCT_ID.get(product.id) === Number(size);
    })
    .sort((a, b) => b.score - a.score)
    .filter(({ score }, _, all) => score === all[0]?.score)
    .map(({ product }) => ({
      productId: product.id,
      sku: product.sku,
      name: product.name,
      priceKobo: product.basePriceKobo,
      stockOnHand: product.stockOnHand,
    }));
}
