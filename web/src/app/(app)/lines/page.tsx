"use client";

import { useMemo, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import type { DetailTab } from "@/components/stats/stats-table-helpers";
import { SectionHeader } from "@/components/ui/section-header";
import type { StatsRow } from "@/lib/types";
import { getLineStatsDetail, getLineStatsHistory, listLineStats } from "@/lib/api-client";

export default function LinesPage() {
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("detail");
  const detailDescription = useMemo(() => {
    if (!selectedLineId) return "Select a row to inspect line details and history trends.";
    const activeView = detailTab === "history" ? "History" : "Detail";
    return `Selected line: ${selectedLineId} · Active view: ${activeView}`;
  }, [detailTab, selectedLineId]);

  return (
    <PageContainer title="Lines" description="Monitor aggregate line performance and repertoire coverage.">
      <PageSection>
        <SectionHeader title="Line performance" description={detailDescription} />
        <StatsTable
          title="Lines"
          description="Aggregated stats by matched repertoire line."
          queryKey={["line-stats"]}
          queryFn={listLineStats}
          rowIdField="key"
          detailQueryKey="line-stats-detail"
          historyQueryKey="line-stats-history"
          fetchDetail={getLineStatsDetail}
          fetchHistory={getLineStatsHistory}
          drilldownLabel="Line details"
          onRowSelectionChange={(_row: StatsRow | null, rowId: string | null) => {
            setSelectedLineId(rowId);
            setDetailTab("detail");
          }}
          onDetailTabChange={setDetailTab}
        />
      </PageSection>
    </PageContainer>
  );
}
