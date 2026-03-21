import { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const variants: Record<ButtonVariant, string> = {
  primary: "border-primary/80 bg-primary text-primary-foreground shadow-soft hover:-translate-y-px hover:border-secondary hover:bg-secondary",
  secondary: "border-border/80 bg-card/95 text-foreground shadow-soft hover:-translate-y-px hover:border-primary/20 hover:bg-elevated",
  ghost: "border-transparent bg-transparent text-muted-foreground hover:border-border/80 hover:bg-hover hover:text-hover-foreground",
  danger: "border-danger bg-danger text-danger-foreground shadow-soft hover:bg-danger/90",
  outline: "border-border/80 bg-transparent text-foreground hover:bg-hover",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
  icon: "h-9 w-9 px-0",
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; children: ReactNode }) {
  return (
    <button
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border font-medium transition duration-200 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
