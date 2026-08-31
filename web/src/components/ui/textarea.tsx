import { forwardRef, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "min-h-28 w-full rounded-control border border-border/50 bg-card px-3.5 py-3 text-sm text-foreground shadow-sm transition-[border-color,box-shadow,background-color] duration-200 placeholder:text-muted-foreground/70 hover:border-border/75 focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/45 aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/25 disabled:cursor-not-allowed disabled:bg-muted/55 disabled:text-muted-foreground/65",
        className,
      )}
      {...props}
    />
  );
});
