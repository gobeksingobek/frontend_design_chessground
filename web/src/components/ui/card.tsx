import { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("grid gap-control-gap rounded-[1.25rem] border border-border/80 bg-card/95 px-card-pad py-card-pad shadow-panel backdrop-blur-sm", className)}>
      {children}
    </div>
  );
}
