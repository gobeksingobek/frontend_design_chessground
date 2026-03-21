"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { DataTableSection, DetailPane, EmptyState } from "@/components/ui/page-patterns";
import { BodyText, CardTitle, CaptionText, MutedText } from "@/components/ui/typography";
import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  const [active, setActive] = useState<number | null>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });
  if (isLoading) return <MutedText>Loading insights…</MutedText>;

  return (
    <PageContainer title="Insights" description="Review generated observations, confidence levels, and supporting evidence references.">
      <PageSection>
        <DataTableSection title="Insights" description="Generated observations with optional supporting evidence references.">
          {data.length === 0 ? <EmptyState title="No insights yet" description="Generated observations will appear here once the backend has enough evidence to summarize." /> : null}
          {data.length > 0 ? (
            <DetailPane className="gap-section-gap">
              {data.map((row, index) => (
                <div key={`${String(row.title)}-${index}`} className="grid gap-4 border-b border-border/60 pb-lg last:border-b-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-sm">
                    <div className="grid gap-2">
                      <CaptionText>Insight #{index + 1}</CaptionText>
                      <CardTitle>{String(row.title ?? "Untitled")}</CardTitle>
                      <BodyText className="text-muted-foreground">Confidence score {Number(row.confidence ?? 0).toFixed(2)}</BodyText>
                    </div>
                    <Button variant="ghost" onClick={() => setActive(active === index ? null : index)}>{active === index ? "Hide evidence" : "Show evidence"}</Button>
                  </div>
                  {active === index ? <div className="grid gap-3 rounded-xl border border-border/70 bg-card px-4 py-4"><CaptionText>Supporting evidence</CaptionText>{(row.source_refs ?? []).length === 0 ? <MutedText>No evidence references were attached to this insight.</MutedText> : <ul className="grid gap-2">{(row.source_refs ?? []).map((ref) => <li key={`${ref.type}-${ref.id}`} className="rounded-lg bg-muted/60 px-3 py-2"><BodyText className="leading-6"><span className="font-medium text-foreground">{ref.label}</span> <span className="text-muted-foreground">({ref.type}:{ref.id})</span></BodyText></li>)}</ul>}</div> : null}
                </div>
              ))}
            </DetailPane>
          ) : null}
        </DataTableSection>
      </PageSection>
    </PageContainer>
  );
}
