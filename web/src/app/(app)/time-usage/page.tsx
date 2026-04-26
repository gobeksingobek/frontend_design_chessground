"use client";

import { useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import { SectionHeader } from "@/components/ui/section-header";
import { listTimeUsageStats } from "@/lib/api-client";
import type { TimeUsagePivot } from "@/lib/types";

const PIVOT_OPTIONS: Array<{ value: TimeUsagePivot; label: string }> = [
  { value: "self_vs_opp", label: "Self vs Opponent" },
  { value: "in_book_vs_out_of_book", label: "In book vs Out of book" },
];

const COLUMN_MODELS: Record<TimeUsagePivot, string[]> = {
  self_vs_opp: ["bucket", "total_games", "total_moves", "avg_time_spent_seconds", "avg_time_spent_fraction"],
  in_book_vs_out_of_book: ["bucket", "total_moves", "avg_time_spent_fraction", "avg_time_spent_seconds", "total_games"],
};

export default function TimeUsagePage() {
  const [pivot, setPivot] = useState<TimeUsagePivot>("self_vs_opp");
  return (
    <PageContainer title="Time Usage" description="Pivot in-book vs. out-of-book time trends to spot decision-making patterns.">
      <PageSection>
        <SectionHeader title="Time usage patterns" description="Use the shared header layout, then pivot the report to compare decision-time behavior." />
        <StatsTable
          title="Time usage"
          description="In-book vs out-of-book time trends."
          queryKey={["time-usage-stats", pivot]}
          queryFn={() => listTimeUsageStats(pivot)}
          pivotOptions={PIVOT_OPTIONS}
          pivotValue={pivot}
          onPivotChange={(value) => setPivot(value as TimeUsagePivot)}
          columnModelsByPivot={COLUMN_MODELS}
        />
      </PageSection>
    </PageContainer>
  );
}
