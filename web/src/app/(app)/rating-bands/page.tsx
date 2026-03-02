"use client";

import { useState } from "react";

import { StatsTable } from "@/components/stats-table";
import { listRatingBandStats } from "@/lib/api-client";

export default function RatingBandsPage() {
  const [bandSize, setBandSize] = useState(100);

  return (
    <div className="stack">
      <label>
        Band size
        <input type="number" min={50} max={400} step={50} value={bandSize} onChange={(e) => setBandSize(Number(e.target.value || 100))} />
      </label>
      <StatsTable
        title="Rating bands"
        description="Aggregated stats by white/black rating bands."
        queryKey={["rating-band-stats", String(bandSize)]}
        queryFn={() => listRatingBandStats(bandSize)}
      />
    </div>
  );
}
