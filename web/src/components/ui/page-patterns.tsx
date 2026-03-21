import { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeader } from "@/components/ui/section-header";
import { CardTitle, MutedText } from "@/components/ui/typography";

export { EmptyState };

export function KpiSummary({ children, className }: { children: ReactNode; className?: string }) {
  return <Card className={cn("gap-grid-gap", className)}>{children}</Card>;
}

export function FilterPanel({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-control-gap border-border/80 bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <MutedText>{description}</MutedText> : null}
      {children}
    </Card>
  );
}

export function DataTableSection({ title, description, actions, children, className }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-grid-gap", className)}>
      {title ? <SectionHeader title={title} description={description} actions={actions} /> : description || actions ? <div className="grid gap-sm">{description ? <MutedText>{description}</MutedText> : null}{actions ? <div className="flex flex-wrap items-center gap-sm">{actions}</div> : null}</div> : null}
      {children}
    </div>
  );
}

export function DetailPane({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-grid-gap bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <MutedText>{description}</MutedText> : null}
      {children}
    </Card>
  );
}

export function DenseControlRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-sm", className)}>{children}</div>;
}

export function InsightCallout({ title, description }: { title: string; description: string }) {
  return <div className="rounded-xl border border-border/70 bg-card px-4 py-4"><CardTitle className="text-base">{title}</CardTitle><MutedText className="mt-2">{description}</MutedText></div>;
}
