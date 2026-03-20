import { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="grid gap-2">
        <h2 className="text-section text-text">{title}</h2>
        {description ? <div className="text-sm text-text-muted">{description}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
