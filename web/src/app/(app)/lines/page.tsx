"use client";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import { SectionHeader } from "@/components/ui/section-header";
import { listLineStats } from "@/lib/api-client";

export default function LinesPage() {
  return (
    <PageContainer title="Lines" description="Monitor aggregate line performance and repertoire coverage.">
      <PageSection>
        <SectionHeader title="Line performance" description="Review aggregate line performance with the same page title placement and intro pattern used across the workspace." />
        <StatsTable title="Lines" description="Aggregated stats by matched repertoire line." queryKey={["line-stats"]} queryFn={listLineStats} />
      </PageSection>
    </PageContainer>
  );
}
