import { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Table({ className, children }: { className?: string; children: ReactNode }) {
  return <div className="overflow-hidden rounded-xl border border-border bg-panel shadow-soft"><table className={cn("min-w-full divide-y divide-border text-sm", className)}>{children}</table></div>;
}

export function TableHead({ children }: { children: ReactNode }) {
  return <thead className="bg-panel-muted/80 text-text-subtle">{children}</thead>;
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border/80">{children}</tbody>;
}

export function Th({ className, children }: { className?: string; children: ReactNode }) {
  return <th className={cn("px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.12em]", className)}>{children}</th>;
}

export function Td({ className, children }: { className?: string; children: ReactNode }) {
  return <td className={cn("px-4 py-3 align-top text-text", className)}>{children}</td>;
}
