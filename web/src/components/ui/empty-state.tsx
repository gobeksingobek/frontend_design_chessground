import { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { CardTitle, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

export function EmptyState({ title = "Nothing to show", description, action, visual, className }: { title?: string; description?: string; action?: ReactNode; visual?: ReactNode; className?: string }) {
  return (
    <Card className={cn("place-items-center gap-control-gap border-dashed border-border/70 bg-card px-6 py-10 text-center", className)}>
      {visual ? <div className="grid place-items-center">{visual}</div> : null}
      <div className="grid gap-2">
        <CardTitle>{title}</CardTitle>
        {description ? <MutedText>{description}</MutedText> : null}
      </div>
      {action}
    </Card>
  );
}
