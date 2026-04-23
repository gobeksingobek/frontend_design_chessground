"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { buildRatingBandSummary, normalizeBandSizeByGuardrails, StatsTable } from "@/components/stats/stats-table";
import { StatCard } from "@/components/ui/stat-card";
import { Select } from "@/components/ui/select";
import { SectionHeader } from "@/components/ui/section-header";
import { listRatingBandStats } from "@/lib/api-client";

const DEFAULT_GUARDRAILS = {
  min: 50,
  max: 400,
  step: 50,
  allowedBandSizes: [50, 100, 150, 200, 250, 300, 350, 400],
  fallback: 100,
};

export default function RatingBandsPage() {
  const [bandSize, setBandSize] = useState(DEFAULT_GUARDRAILS.fallback);
  const normalizedBandSize = useMemo(() => normalizeBandSizeByGuardrails(bandSize, DEFAULT_GUARDRAILS), [bandSize]);
  const statsQuery = useQuery({
    queryKey: ["rating-band-stats", String(normalizedBandSize)],
    queryFn: () => listRatingBandStats(normalizedBandSize),
  });
  const metadataGuardrails = useMemo(() => {
    const allowedFromApi = statsQuery.data?.allowed_band_sizes ?? DEFAULT_GUARDRAILS.allowedBandSizes;
    return {
      ...DEFAULT_GUARDRAILS,
      allowedBandSizes: allowedFromApi,
    };
  }, [statsQuery.data?.allowed_band_sizes]);
  const safeBandSize = useMemo(() => normalizeBandSizeByGuardrails(normalizedBandSize, metadataGuardrails), [metadataGuardrails, normalizedBandSize]);
  const summaryBlocks = useMemo(() => buildRatingBandSummary(statsQuery.data), [statsQuery.data]);

  return (
    <PageContainer title="Rating Bands" description="Compare performance by rating segments and adjust the resolution of the report.">
      <PageSection>
        <SectionHeader title="Rating band trends" description="Use the shared intro layout, then adjust the report resolution before scanning the table." />
        <label className="grid max-w-xs gap-2 rounded-2xl border border-border bg-panel px-4 py-4 text-sm text-text-subtle shadow-soft">Band size<Select value={safeBandSize} onChange={(e) => setBandSize(Number(e.target.value))}>{metadataGuardrails.allowedBandSizes.map((size) => <option key={size} value={size}>{size}</option>)}</Select></label>
        {summaryBlocks.length > 0 ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{summaryBlocks.map((item) => <StatCard key={item.label} label={item.label} value={item.value} />)}</div> : null}
        <StatsTable title="Rating bands" description="Aggregated stats by white/black rating bands." queryKey={["rating-band-stats", String(safeBandSize)]} queryFn={() => listRatingBandStats(safeBandSize)} />
      </PageSection>
    </PageContainer>
  );
}
