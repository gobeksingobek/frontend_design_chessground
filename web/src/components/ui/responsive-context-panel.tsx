"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

export function resolveFocusWrapTarget(shiftKey: boolean, activeIsFirst: boolean, activeIsLast: boolean): "first" | "last" | null {
  if (shiftKey && activeIsFirst) return "last";
  if (!shiftKey && activeIsLast) return "first";
  return null;
}

export function ResponsiveContextPanel({
  children,
  label = "Workspace context",
  className,
}: {
  children: ReactNode;
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const trigger = triggerRef.current;
    document.body.style.overflow = "hidden";
    const panel = panelRef.current;
    const focusables = panel ? Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
    (focusables[0] ?? panel)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "Tab" || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables.at(-1);
      const wrapTarget = resolveFocusWrapTarget(event.shiftKey, document.activeElement === first, document.activeElement === last);
      if (wrapTarget === "last") {
        event.preventDefault();
        last?.focus();
      } else if (wrapTarget === "first") {
        event.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      trigger?.focus();
    };
  }, [open]);

  return (
    <>
      <aside className={cn("hidden min-w-0 gap-4 xl:sticky xl:top-24 xl:grid xl:self-start", className)} aria-label={label}>
        {children}
      </aside>
      <div className="flex justify-end xl:hidden">
        <Button ref={triggerRef} type="button" variant="outline" size="sm" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}>
          <PanelIcon />
          {label}
        </Button>
      </div>
      {open ? (
        <div className="fixed inset-0 z-[70] xl:hidden">
          <button type="button" className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setOpen(false)} aria-label={`Close ${label}`} />
          <aside
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            tabIndex={-1}
            className="absolute inset-x-0 bottom-0 grid max-h-[86vh] gap-4 overflow-y-auto rounded-t-card border border-border/40 bg-glass/96 p-4 shadow-panel backdrop-blur-xl md:inset-y-0 md:left-auto md:w-[24rem] md:max-h-none md:rounded-l-card md:rounded-tr-none md:p-5"
          >
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-border/35 bg-glass/95 pb-3">
              <h2 className="text-base font-semibold tracking-tight text-foreground">{label}</h2>
              <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>Close</Button>
            </div>
            {children}
          </aside>
        </div>
      ) : null}
    </>
  );
}

function PanelIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M15 4v16" /></svg>;
}
