"use client";

import { StatsTable } from "@/components/stats-table";
import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  return (
    <StatsTable
      title="Insights"
      description="Derived conclusions from analyzed games and repertoire coverage."
      queryKey={["insights"]}
      queryFn={listInsights}
    />
  );
}
