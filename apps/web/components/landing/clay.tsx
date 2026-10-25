import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * Clay renders generated in Google Flow (Nano Banana), saved in public/brand.
 * Each sits on the page's paper colour, so they're blended with multiply and
 * feathered at the edges to hide the square frame.
 */
export const CLAY = {
  mascot: { src: "/brand/mascot.jpg", alt: "Sowo, a terracotta clay mascot in an indigo and mustard headtie, sitting on a wooden stool with a phone" },
  wave: { src: "/brand/pose-wave.jpg", alt: "Sowo waving hello" },
  haggle: { src: "/brand/pose-haggle.jpg", alt: "Sowo holding up a price tag with a cheeky smile" },
  coin: { src: "/brand/pose-coin.jpg", alt: "Sowo hugging a gold coin with a padlock on it" },
  pack: { src: "/brand/pose-pack.jpg", alt: "Sowo taping up a cardboard box" },
  night: { src: "/brand/pose-night.jpg", alt: "Sowo awake on its stool at night, next to a clay moon and stars" },
  loafer: { src: "/brand/obj-loafer.jpg", alt: "" },
  coins: { src: "/brand/obj-coins.jpg", alt: "" },
  padlock: { src: "/brand/obj-padlock.jpg", alt: "" },
  receipt: { src: "/brand/obj-receipt.jpg", alt: "" },
  phone: { src: "/brand/obj-phone.jpg", alt: "" },
  bag: { src: "/brand/obj-bag.jpg", alt: "" },
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
      sizes={`${size}px`}
      draggable={false}
      className={cn(
        "select-none mix-blend-multiply [mask-image:radial-gradient(closest-side,#000_72%,transparent)]",
        className,
      )}
    />
  );
}
