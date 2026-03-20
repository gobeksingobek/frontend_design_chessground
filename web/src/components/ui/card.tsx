import { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("grid gap-4 rounded-xl border border-border bg-card px-xl py-xl shadow-panel", className)}>
      {children}
    </div>
  );
}
