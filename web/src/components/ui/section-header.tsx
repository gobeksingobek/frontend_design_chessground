import { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { MutedText, SectionTitle } from "@/components/ui/typography";

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
        <SectionTitle>{title}</SectionTitle>
        {description ? <MutedText as="div" className="max-w-3xl">{description}</MutedText> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
