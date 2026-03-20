"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";
import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  const [active, setActive] = useState<number | null>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });
  if (isLoading) return <p className="text-sm text-text-muted">Loading insights…</p>;

  return (
    <div className="grid gap-4">
      <SectionHeader title="Insights" description="Generated observations with optional supporting evidence references." />
      <Card>
        {(data ?? []).map((row, index) => (
          <div key={`${String(row.title)}-${index}`} className="grid gap-2 border-b border-border/60 pb-3 last:border-b-0 last:pb-0">
            <div className="flex flex-wrap items-center gap-2"><strong>#{index + 1}</strong><span>{String(row.title ?? "Untitled")} · confidence {Number(row.confidence ?? 0).toFixed(2)}</span><Button variant="ghost" onClick={() => setActive(active === index ? null : index)}>Evidence</Button></div>
            {active === index ? <ul className="grid gap-1 text-sm text-text-subtle">{(row.source_refs ?? []).map((ref) => <li key={`${ref.type}-${ref.id}`}>{ref.label} ({ref.type}:{ref.id})</li>)}</ul> : null}
          </div>
        ))}
      </Card>
    </div>
  );
}
