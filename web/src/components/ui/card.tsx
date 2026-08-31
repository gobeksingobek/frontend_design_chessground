import { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

const cardVariants = {
  default: "border-border/45 bg-card px-card-pad py-card-pad shadow-panel",
  workspace: "border-border/45 bg-elevated px-card-pad py-card-pad shadow-panel md:px-3xl md:py-3xl",
  workspacePanel: "border-border/40 bg-card px-card-pad py-card-pad shadow-soft",
  utility: "border-border/40 bg-muted/65 px-lg py-lg shadow-soft",
  soft: "border-border/40 bg-elevated px-card-pad py-card-pad shadow-soft",
  glass: "border-border/35 bg-glass/82 px-card-pad py-card-pad shadow-panel backdrop-blur-xl",
} as const;

export type CardVariant = keyof typeof cardVariants;

export function Card({
  className,
  children,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLDivElement> & { className?: string; children: ReactNode; variant?: CardVariant }) {
  return (
    <div className={cn("grid gap-control-gap rounded-card border", cardVariants[variant], className)} {...props}>
      {children}
    </div>
  );
}
