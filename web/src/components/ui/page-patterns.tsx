import { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";

export function KpiSummary({ children, className }: { children: ReactNode; className?: string }) {
  return <Card className={cn("gap-grid-gap", className)}>{children}</Card>;
}

export function FilterPanel({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-control-gap border-border/80 bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      {children}
    </Card>
  );
}

export function DataTableSection({ title, description, actions, children, className }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-grid-gap", className)}>
      {title ? <SectionHeader title={title} description={description} actions={actions} /> : description || actions ? <div className="grid gap-sm">{description ? <p className="text-sm text-muted-foreground">{description}</p> : null}{actions ? <div className="flex flex-wrap items-center gap-sm">{actions}</div> : null}</div> : null}
      {children}
    </div>
  );
}

export function DetailPane({ title, description, children, className }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-grid-gap bg-elevated", className)}>
      {title ? <SectionHeader title={title} description={description} /> : description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      {children}
    </Card>
  );
}

export function EmptyState({ title = "Nothing to show", description, action, className }: { title?: string; description?: string; action?: ReactNode; className?: string }) {
  return (
    <Card className={cn("place-items-center gap-control-gap border-dashed border-border/80 bg-elevated py-3xl text-center", className)}>
      <div className="grid max-w-2xl gap-sm">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </Card>
  );
}

export function DenseControlRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-sm", className)}>{children}</div>;
}
