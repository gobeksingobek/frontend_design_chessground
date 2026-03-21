"use client";

import { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CardTitle, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

export function Dialog({ open, onClose, title, description, children, footer, className }: { open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; className?: string }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-bg/80 p-4 backdrop-blur-sm">
      <Card className={cn("w-full max-w-2xl gap-4 border-border bg-panel", className)}>
        <div className="flex items-start justify-between gap-4">
          <div className="grid gap-1">
            <CardTitle>{title}</CardTitle>
            {description ? <MutedText>{description}</MutedText> : null}
          </div>
          <Button type="button" size="icon" variant="ghost" onClick={onClose} aria-label="Close dialog">×</Button>
        </div>
        <div>{children}</div>
        {footer ? <div className="flex flex-wrap justify-end gap-2">{footer}</div> : null}
      </Card>
    </div>
  );
}
