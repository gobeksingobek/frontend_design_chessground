"use client";

import { ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({
  items,
  defaultValue,
  value,
  onValueChange,
  className,
}: {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
}) {
  const initial = defaultValue ?? items[0]?.id ?? "";
  const [internalActive, setInternalActive] = useState(initial);
  const active = value ?? internalActive;
  const current = items.find((item) => item.id == active) ?? items[0];
  const setActive = (next: string) => {
    if (value == null) {
      setInternalActive(next);
    }
    onValueChange?.(next);
  };

  return (
    <div className={cn("grid gap-4", className)}>
      <div className="flex flex-wrap gap-1 border-b border-border/40 pb-2" role="tablist">
        {items.map((item) => (
          <Button key={item.id} type="button" role="tab" aria-selected={item.id === current?.id} size="sm" variant={item.id === current?.id ? "primary" : "ghost"} onClick={() => setActive(item.id)}>
            {item.label}
          </Button>
        ))}
      </div>
      <div role="tabpanel">{current?.content}</div>
    </div>
  );
}
