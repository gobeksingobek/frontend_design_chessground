import { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-md border border-border bg-panel-muted px-4 py-2 text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-60",
        props.className,
      )}
      {...props}
    />
  );
}
