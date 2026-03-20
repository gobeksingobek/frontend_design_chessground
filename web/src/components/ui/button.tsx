import { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<ButtonVariant, string> = {
  primary: "border-accent bg-accent text-slate-950 hover:bg-accent-strong",
  secondary: "border-border bg-panel-muted text-text hover:bg-panel-elevated",
  ghost: "border-transparent bg-transparent text-text-muted hover:border-border hover:bg-panel-muted hover:text-text",
  danger: "border-danger bg-danger text-white hover:opacity-90",
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
        "inline-flex items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
