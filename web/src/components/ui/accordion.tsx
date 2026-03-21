"use client";

import { ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

export function AccordionItem({ title, subtitle, children, defaultOpen = false, className }: { title: ReactNode; subtitle?: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card className={cn("gap-4", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="grid gap-1">
          <div className="text-base font-semibold text-foreground">{title}</div>
          {subtitle ? <div className="text-sm text-muted-foreground">{subtitle}</div> : null}
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen((value) => !value)}>{open ? "Collapse" : "Expand"}</Button>
      </div>
      {open ? <div>{children}</div> : null}
    </Card>
  );
}
