"use client";

import { useQuery } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { DetailPane, EmptyState } from "@/components/ui/page-patterns";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";
import { listInsights } from "@/lib/api-client";

function confidenceTone(confidence: number): "success" | "warning" | "accent" {
  if (confidence >= 0.8) return "success";
  if (confidence >= 0.55) return "accent";
  return "warning";
}

export default function InsightsPage() {
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });

  return (
    <PageContainer title="Insights" description="Review generated observations through confidence-led cards with supporting evidence and clearer hierarchy.">
      <PageSection>
        <SectionHeader title="Insight summaries" description="Each card separates the thesis, confidence, and evidence so you can validate what to trust first." />

        {isLoading ? <div className="grid gap-4 lg:grid-cols-2">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-64 rounded-xl" />)}</div> : null}
        {!isLoading && data.length === 0 ? <EmptyState title="No insights yet" description="Generated observations will appear here once the backend has enough evidence to summarize." /> : null}
        {!isLoading && data.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {data.map((row, index) => {
              const confidence = Number(row.confidence ?? 0);
              const evidence = row.source_refs ?? [];
              return (
                <DetailPane key={`${String(row.title)}-${index}`} className="gap-5 bg-card">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="grid gap-2">
                      <CaptionText>Insight #{index + 1}</CaptionText>
                      <CardTitle className="text-lg">{String(row.title ?? "Untitled")}</CardTitle>
                    </div>
                    <Badge tone={confidenceTone(confidence)}>Confidence {confidence.toFixed(2)}</Badge>
                  </div>

                  <div className="grid gap-3 rounded-xl border border-border/70 bg-muted/40 px-4 py-4">
                    <CaptionText>Summary</CaptionText>
                    <MutedText>{String(row.summary ?? row.description ?? "No summary was provided for this insight.")}</MutedText>
                  </div>

                  <div className="grid gap-3">
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle className="text-base">Evidence</CardTitle>
                      <Badge variant="outline">{evidence.length} references</Badge>
                    </div>
                    {evidence.length === 0 ? <MutedText className="rounded-xl border border-border/70 bg-card px-4 py-4">No evidence references were attached to this insight.</MutedText> : <ul className="grid gap-2">{evidence.map((ref) => <li key={`${ref.type}-${ref.id}`} className="rounded-xl border border-border/70 bg-card px-4 py-3 text-sm"><div className="font-medium text-foreground">{ref.label}</div><div className="mt-1 text-muted-foreground">{ref.type}:{ref.id}</div></li>)}</ul>}
                  </div>
                </DetailPane>
              );
            })}
          </div>
        ) : null}
      </PageSection>
    </PageContainer>
  );
}
