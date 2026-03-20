import { ReactNode } from "react";

import { cn } from "@/lib/cn";

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "accent";

const tones: Record<BadgeTone, string> = {
  neutral: "border-border bg-panel-muted text-text-muted",
  success: "border-success/40 bg-success/15 text-success",
  warning: "border-warning/40 bg-warning/15 text-warning",
  danger: "border-danger/40 bg-danger/15 text-danger",
  accent: "border-accent/40 bg-accent/15 text-accent",
};

export function Badge({ className, tone = "neutral", children }: { className?: string; tone?: BadgeTone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center rounded-pill border px-3 py-1 text-xs font-medium", tones[tone], className)}>{children}</span>;
}
