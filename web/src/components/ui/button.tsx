import { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<ButtonVariant, string> = {
  primary: "border-primary bg-primary text-primary-foreground hover:border-secondary hover:bg-secondary",
  secondary: "border-border bg-card text-foreground hover:border-primary/20 hover:bg-elevated",
  ghost: "border-transparent bg-transparent text-muted-foreground hover:border-border hover:bg-hover hover:text-hover-foreground",
  danger: "border-danger bg-danger text-danger-foreground hover:bg-danger/90",
};

export function Button({
  className,
  variant = "secondary",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; children: ReactNode }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
