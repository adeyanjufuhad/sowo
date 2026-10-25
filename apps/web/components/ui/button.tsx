import { cva, type VariantProps } from "class-variance-authority";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group inline-flex items-center justify-center gap-3 rounded-full font-medium whitespace-nowrap select-none transition-[background-color,color,box-shadow,transform] duration-300 ease-(--ease-smooth) active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-accent-strong text-white shadow-[0_10px_24px_-12px_rgba(184,60,25,0.7),inset_0_1px_0_rgba(255,255,255,0.18)] hover:bg-[#a33515]",
        secondary:
          "bg-card text-ink ring-1 ring-line shadow-[0_6px_18px_-12px_rgba(31,26,23,0.35)] hover:bg-white",
        ghost: "text-ink-soft hover:text-ink hover:bg-paper-deep",
        dark: "bg-paper text-night hover:bg-white",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-5 text-[15px]",
        lg: "h-13 pl-6 pr-2 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonLinkProps = ComponentProps<typeof Link> &
  VariantProps<typeof buttonVariants> & {
    /** Trailing icon, rendered in its own circle (button-in-button). */
    icon?: ReactNode;
  };

export function ButtonLink({ className, variant, size, icon, children, ...props }: ButtonLinkProps) {
  return (
    <Link className={cn(buttonVariants({ variant, size }), icon && size === "lg" && "pr-2", className)} {...props}>
      <span>{children}</span>
      {icon ? (
        <span
          aria-hidden
          className={cn(
            "grid size-9 place-items-center rounded-full transition-transform duration-300 ease-(--ease-spring) group-hover:translate-x-0.5 group-hover:-translate-y-px",
            variant === "secondary" || variant === "dark" ? "bg-ink/5" : "bg-white/15",
          )}
        >
          {icon}
        </span>
      ) : null}
    </Link>
  );
}

export { buttonVariants };
