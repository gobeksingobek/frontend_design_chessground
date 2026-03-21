import { ReactNode } from "react";

import { cn } from "@/lib/cn";

const cardVariants = {
  default: "border-border/80 bg-card/95 px-card-pad py-card-pad shadow-panel backdrop-blur-sm",
  workspace: "border-border/90 bg-elevated/95 px-card-pad py-card-pad shadow-panel backdrop-blur-md md:px-3xl md:py-3xl",
  utility: "border-border/60 bg-muted/55 px-lg py-lg shadow-soft backdrop-blur-sm",
  soft: "border-border/70 bg-elevated/70 px-card-pad py-card-pad shadow-soft backdrop-blur-sm",
} as const;

export type CardVariant = keyof typeof cardVariants;

export function Card({
  className,
  children,
  variant = "default",
}: {
  className?: string;
  children: ReactNode;
  variant?: CardVariant;
}) {
  return (
    <div className={cn("grid gap-control-gap rounded-[1.25rem] border", cardVariants[variant], className)}>
      {children}
    </div>
  );
}
