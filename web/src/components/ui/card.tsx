import { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("grid gap-control-gap rounded-xl border border-border bg-card px-card-pad py-card-pad shadow-panel", className)}>
      {children}
    </div>
  );
}
