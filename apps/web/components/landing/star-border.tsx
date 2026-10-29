import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";

/** React Bits' StarBorder: a slow glow travelling along the rim of a button. */
export function StarBorder({
  children,
  className,
  color = "#ffd9a8",
  speed = 6,
}: {
  children: ReactNode;
  className?: string;
  color?: string;
  speed?: number;
}) {
  const glow = {
    background: `radial-gradient(circle, ${color}, transparent 10%)`,
    ["--star-speed" as string]: `${speed}s`,
  } as CSSProperties;

  return (
    <span className={cn("relative inline-block rounded-full", className)}>
      <span aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-full">
        <span className="star-border-bottom absolute right-[-250%] bottom-[-11px] h-1/2 w-[300%] rounded-full opacity-80 blur-[1px]" style={glow} />
        <span className="star-border-top absolute top-[-10px] left-[-250%] h-1/2 w-[300%] rounded-full opacity-80 blur-[1px]" style={glow} />
      </span>
      <span className="relative z-[1] block rounded-full p-[1.5px]">{children}</span>
    </span>
  );
}
