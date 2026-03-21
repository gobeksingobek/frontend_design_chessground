"use client";

import { useQuery } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { AccordionItem } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { DataTableSection, EmptyState, InsightCallout } from "@/components/ui/page-patterns";
import { Skeleton } from "@/components/ui/skeleton";
import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });
  return (
    <PageContainer title="Insights" description="Review generated observations, confidence levels, and supporting evidence references.">
      <PageSection>
        <DataTableSection title="Insights" description="Each card groups an observation with its evidence so you can scan, expand, and validate it quickly.">
          {isLoading ? <div className="grid gap-4">{Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-36 rounded-xl" />)}</div> : null}
          {!isLoading && data.length === 0 ? <EmptyState title="No insights yet" description="Generated observations will appear here once the backend has enough evidence to summarize." /> : null}
          {!isLoading && data.length > 0 ? (
            <div className="grid gap-4">
              {data.map((row, index) => (
                <AccordionItem
                  key={`${String(row.title)}-${index}`}
                  title={String(row.title ?? "Untitled")}
                  subtitle={`Insight #${index + 1}`}
                  defaultOpen={index === 0}
                >
                  <div className="grid gap-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="accent">Confidence {Number(row.confidence ?? 0).toFixed(2)}</Badge>
                      <Badge variant="outline">{(row.source_refs ?? []).length} evidence refs</Badge>
                    </div>
                    <InsightCallout title="Why this matters" description={String(row.summary ?? row.description ?? "No summary was provided for this insight.")} />
                    <div className="grid gap-3 rounded-xl border border-border/70 bg-card px-4 py-4">
                      <h3 className="text-sm font-semibold text-foreground">Supporting evidence</h3>
                      {(row.source_refs ?? []).length === 0 ? <p className="text-sm text-muted-foreground">No evidence references were attached to this insight.</p> : <ul className="grid gap-2">{(row.source_refs ?? []).map((ref) => <li key={`${ref.type}-${ref.id}`} className="rounded-lg border border-border/60 bg-muted/60 px-3 py-2 text-sm"><span className="font-medium text-foreground">{ref.label}</span><span className="ml-2 text-muted-foreground">({ref.type}:{ref.id})</span></li>)}</ul>}
                    </div>
                  </div>
                </AccordionItem>
              ))}
            </div>
          ) : null}
        </DataTableSection>
      </PageSection>
    </PageContainer>
  );
}
