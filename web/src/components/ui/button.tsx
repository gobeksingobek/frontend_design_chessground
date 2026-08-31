import { ButtonHTMLAttributes, forwardRef, ReactNode } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const variants: Record<ButtonVariant, string> = {
  primary: "border-primary/70 bg-primary text-primary-foreground shadow-soft hover:border-primary hover:bg-primary/90 active:bg-primary/80",
  secondary: "border-border/50 bg-card text-foreground shadow-soft hover:border-primary/30 hover:bg-elevated active:bg-muted",
  ghost: "border-transparent bg-transparent text-muted-foreground hover:border-border/45 hover:bg-hover hover:text-hover-foreground active:bg-muted",
  danger: "border-danger bg-danger text-danger-foreground shadow-soft hover:bg-danger/90",
  outline: "border-border/55 bg-transparent text-foreground hover:border-primary/35 hover:bg-hover active:bg-muted",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
  icon: "h-9 w-9 px-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; children: ReactNode }>(function Button({
  className,
  variant = "secondary",
  size = "md",
  children,
  ...props
}, ref) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-control border font-medium transition-[color,background-color,border-color,box-shadow,opacity] duration-200 disabled:cursor-not-allowed disabled:border-border/30 disabled:bg-muted/45 disabled:text-muted-foreground/60 disabled:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/65 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
});
