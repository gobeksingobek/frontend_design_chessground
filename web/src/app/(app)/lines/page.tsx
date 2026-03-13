"use client";

import { StatsTable } from "@/components/stats/stats-table";
import { listLineStats } from "@/lib/api-client";

export default function LinesPage() {
  return (
    <StatsTable
      title="Lines"
      description="Aggregated stats by matched repertoire line."
      queryKey={["line-stats"]}
      queryFn={listLineStats}
    />
  );
}
