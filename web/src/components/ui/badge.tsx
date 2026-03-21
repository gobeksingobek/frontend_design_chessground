import { ReactNode } from "react";

import { cn } from "@/lib/cn";

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "accent";
type BadgeVariant = "soft" | "outline";

const tones: Record<BadgeTone, Record<BadgeVariant, string>> = {
  neutral: {
    soft: "border-border bg-muted text-muted-foreground",
    outline: "border-border/80 bg-transparent text-muted-foreground",
  },
  success: {
    soft: "border-success/30 bg-success/15 text-success",
    outline: "border-success/40 bg-transparent text-success",
  },
  warning: {
    soft: "border-warning/30 bg-warning/15 text-warning",
    outline: "border-warning/40 bg-transparent text-warning",
  },
  danger: {
    soft: "border-danger/30 bg-danger/15 text-danger",
    outline: "border-danger/40 bg-transparent text-danger",
  },
  accent: {
    soft: "border-primary/30 bg-primary/15 text-primary",
    outline: "border-primary/40 bg-transparent text-primary",
  },
};

export function Badge({ className, tone = "neutral", variant = "soft", children }: { className?: string; tone?: BadgeTone; variant?: BadgeVariant; children: ReactNode }) {
  return <span className={cn("inline-flex items-center rounded-pill border px-3 py-1 text-xs font-medium", tones[tone][variant], className)}>{children}</span>;
}
