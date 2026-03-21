"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { DataTableSection, DetailPane, EmptyState } from "@/components/ui/page-patterns";
import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  const [active, setActive] = useState<number | null>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });
  if (isLoading) return <p className="text-sm text-text-muted">Loading insights…</p>;

  return (
    <PageContainer title="Insights" description="Review generated observations, confidence levels, and supporting evidence references.">
      <PageSection>
        <DataTableSection title="Insights" description="Generated observations with optional supporting evidence references.">
          {data.length === 0 ? <EmptyState title="No insights yet" description="Generated observations will appear here once the backend has enough evidence to summarize." /> : null}
          {data.length > 0 ? (
            <DetailPane className="gap-section-gap">
              {data.map((row, index) => (
                <div key={`${String(row.title)}-${index}`} className="grid gap-control-gap border-b border-border/60 pb-lg last:border-b-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-sm">
                    <div className="flex min-w-0 flex-wrap items-center gap-sm text-sm text-foreground">
                      <strong>#{index + 1}</strong>
                      <span>{String(row.title ?? "Untitled")} · confidence {Number(row.confidence ?? 0).toFixed(2)}</span>
                    </div>
                    <Button variant="ghost" onClick={() => setActive(active === index ? null : index)}>Evidence</Button>
                  </div>
                  {active === index ? <ul className="grid gap-xs text-sm text-text-subtle">{(row.source_refs ?? []).map((ref) => <li key={`${ref.type}-${ref.id}`}>{ref.label} ({ref.type}:{ref.id})</li>)}</ul> : null}
                </div>
              ))}
            </DetailPane>
          ) : null}
        </DataTableSection>
      </PageSection>
    </PageContainer>
  );
}
