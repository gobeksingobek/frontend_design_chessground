"use client";

import { useState } from "react";

import { StatsTable } from "@/components/stats/stats-table";
import { Select } from "@/components/ui/select";
import { listTimeUsageStats } from "@/lib/api-client";
import type { TimeUsagePivot } from "@/lib/types";

const PIVOTS: TimeUsagePivot[] = ["month", "result", "compliance"];

export default function TimeUsagePage() {
  const [pivot, setPivot] = useState<TimeUsagePivot>("month");
  return <div className="grid gap-4"><label className="grid max-w-xs gap-2 text-sm text-text-subtle">Pivot<Select value={pivot} onChange={(e) => setPivot(e.target.value as TimeUsagePivot)}>{PIVOTS.map((option) => <option key={option} value={option}>{option}</option>)}</Select></label><StatsTable title="Time usage" description="In-book vs out-of-book time trends." queryKey={["time-usage-stats", pivot]} queryFn={() => listTimeUsageStats(pivot)} /></div>;
}
