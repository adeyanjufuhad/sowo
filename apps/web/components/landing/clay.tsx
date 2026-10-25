import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * Clay renders generated in Google Flow (Nano Banana), saved in public/brand.
 * The paper colour (#f5f1ea) is baked into each file, so they sit seamlessly on
 * bg-paper. They're already small WebPs, so Next serves them untouched: its
 * re-encoding would shift the edge colour and show the square.
 */
export const CLAY = {
  mascot: { src: "/brand/mascot.webp", alt: "Sowo, a terracotta clay mascot in an indigo and mustard headtie, sitting on a wooden stool with a phone" },
  wave: { src: "/brand/pose-wave.webp", alt: "Sowo waving hello" },
  haggle: { src: "/brand/pose-haggle.webp", alt: "Sowo holding up a price tag with a cheeky smile" },
  coin: { src: "/brand/pose-coin.webp", alt: "Sowo hugging a gold coin with a padlock on it" },
  pack: { src: "/brand/pose-pack.webp", alt: "Sowo taping up a cardboard box" },
  night: { src: "/brand/pose-night.webp", alt: "Sowo awake on its stool at night, next to a clay moon and stars" },
  loafer: { src: "/brand/obj-loafer.webp", alt: "" },
  coins: { src: "/brand/obj-coins.webp", alt: "" },
  padlock: { src: "/brand/obj-padlock.webp", alt: "" },
  receipt: { src: "/brand/obj-receipt.webp", alt: "" },
  phone: { src: "/brand/obj-phone.webp", alt: "" },
  bag: { src: "/brand/obj-bag.webp", alt: "" },
} as const;

export type ClayName = keyof typeof CLAY;

export function Clay({
  name,
  size,
  className,
  priority = false,
  decorative = false,
}: {
  name: ClayName;
  /** Rendered width and height in CSS pixels at the largest breakpoint. */
  size: number;
  className?: string;
  priority?: boolean;
  decorative?: boolean;
}) {
  const image = CLAY[name];
  return (
    <Image
      src={image.src}
      alt={decorative ? "" : image.alt}
      width={size}
      height={size}
      priority={priority}
      unoptimized
      draggable={false}
      className={cn(
        "select-none",
        className,
      )}
    />
  );
}
