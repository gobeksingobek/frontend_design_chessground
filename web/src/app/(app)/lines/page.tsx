"use client";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import { listLineStats } from "@/lib/api-client";

export default function LinesPage() {
  return <PageContainer title="Lines" description="Monitor aggregate line performance and repertoire coverage."><PageSection><StatsTable title="Lines" description="Aggregated stats by matched repertoire line." queryKey={["line-stats"]} queryFn={listLineStats} /></PageSection></PageContainer>;
}
