import { ReactNode } from "react";

import { FieldLabel, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

export function FormField({ label, htmlFor, helpText, error, required, children, className }: { label: string; htmlFor?: string; helpText?: string; error?: string | null; required?: boolean; children: ReactNode; className?: string }) {
  return (
    <label htmlFor={htmlFor} className={cn("grid gap-2", className)}>
      <div className="flex items-center gap-2">
        <FieldLabel as="span">{label}</FieldLabel>
        {required ? <span className="text-xs text-muted-foreground">Required</span> : null}
      </div>
      {children}
      {error ? <span className="text-sm text-danger">{error}</span> : helpText ? <MutedText as="span" className="text-sm leading-6">{helpText}</MutedText> : null}
    </label>
  );
}
