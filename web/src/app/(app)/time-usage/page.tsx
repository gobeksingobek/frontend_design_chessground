"use client";

import { useState } from "react";

import { StatsTable } from "@/components/stats/stats-table";
import { listTimeUsageStats } from "@/lib/api-client";
import type { TimeUsagePivot } from "@/lib/types";

const PIVOTS: TimeUsagePivot[] = ["month", "result", "compliance"];

export default function TimeUsagePage() {
  const [pivot, setPivot] = useState<TimeUsagePivot>("month");

  return (
    <div className="stack">
      <label>
        Pivot
        <select value={pivot} onChange={(e) => setPivot(e.target.value as TimeUsagePivot)}>
          {PIVOTS.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>
      <StatsTable
        title="Time usage"
        description="In-book vs out-of-book time trends."
        queryKey={["time-usage-stats", pivot]}
        queryFn={() => listTimeUsageStats(pivot)}
      />
    </div>
  );
}
