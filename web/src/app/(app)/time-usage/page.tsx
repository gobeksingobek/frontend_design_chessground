"use client";

import { useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import { Select } from "@/components/ui/select";
import { listTimeUsageStats } from "@/lib/api-client";
import type { TimeUsagePivot } from "@/lib/types";

const PIVOTS: TimeUsagePivot[] = ["month", "result", "compliance"];

export default function TimeUsagePage() {
  const [pivot, setPivot] = useState<TimeUsagePivot>("month");
  return <PageContainer title="Time Usage" description="Pivot in-book vs. out-of-book time trends to spot decision-making patterns."><PageSection><label className="grid max-w-xs gap-2 rounded-2xl border border-border bg-panel px-4 py-4 text-sm text-text-subtle shadow-soft">Pivot<Select value={pivot} onChange={(e) => setPivot(e.target.value as TimeUsagePivot)}>{PIVOTS.map((option) => <option key={option} value={option}>{option}</option>)}</Select></label><StatsTable title="Time usage" description="In-book vs out-of-book time trends." queryKey={["time-usage-stats", pivot]} queryFn={() => listTimeUsageStats(pivot)} /></PageSection></PageContainer>;
}
