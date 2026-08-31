import { HTMLAttributes, ReactNode, TableHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Table({ className, children, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("min-w-full divide-y divide-border text-body leading-7", className)} {...props}>{children}</table>;
}

export function TableContainer({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("overflow-x-auto rounded-card border border-border/45 bg-card shadow-soft", className)}>{children}</div>;
}

export function TableHead({ className, children }: { className?: string; children: ReactNode }) {
  return <thead className={cn("bg-muted/70 text-muted-foreground", className)}>{children}</thead>;
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border/35 bg-card">{children}</tbody>;
}

export function TableRow({ className, children, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors duration-150 hover:bg-hover/60", className)} {...props}>{children}</tr>;
}

export function Th({ className, children }: { className?: string; children: ReactNode }) {
  return <th className={cn("whitespace-nowrap px-4 py-3 text-left text-caption font-semibold uppercase tracking-[0.12em]", className)}>{children}</th>;
}

export function Td({ className, children }: { className?: string; children: ReactNode }) {
  return <td className={cn("px-4 py-3.5 align-top text-body leading-7 text-foreground", className)}>{children}</td>;
}
