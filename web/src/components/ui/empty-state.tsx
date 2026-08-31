import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { CardTitle, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

export function EmptyState({ title = "Nothing to show", description, action, visual, className }: { title?: string; description?: string; action?: ReactNode; visual?: ReactNode; className?: string }) {
  return (
    <Card className={cn("place-items-center gap-control-gap border-dashed border-border/55 bg-elevated px-6 py-10 text-center shadow-none", className)}>
      <div className="grid h-10 w-10 place-items-center rounded-full border border-primary/20 bg-primary/10 text-primary" aria-hidden={visual ? undefined : true}>
        {visual ?? <span className="font-mono text-sm font-semibold">CG</span>}
      </div>
      <div className="grid gap-2">
        <CardTitle>{title}</CardTitle>
        {description ? <MutedText>{description}</MutedText> : null}
      </div>
      {action}
    </Card>
  );
}
