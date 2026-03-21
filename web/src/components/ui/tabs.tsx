"use client";

import { ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({ items, defaultValue, className }: { items: TabItem[]; defaultValue?: string; className?: string }) {
  const initial = defaultValue ?? items[0]?.id ?? "";
  const [active, setActive] = useState(initial);
  const current = items.find((item) => item.id == active) ?? items[0];

  return (
    <div className={cn("grid gap-4", className)}>
      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {items.map((item) => (
          <Button key={item.id} type="button" size="sm" variant={item.id === current?.id ? "primary" : "ghost"} onClick={() => setActive(item.id)}>
            {item.label}
          </Button>
        ))}
      </div>
      <div>{current?.content}</div>
    </div>
  );
}
