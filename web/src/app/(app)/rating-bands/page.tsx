"use client";

import { useMemo, useState } from "react";

import { StatsTable } from "@/components/stats/stats-table";
import { listRatingBandStats } from "@/lib/api-client";

const ALLOWED_BAND_SIZES = [50, 100, 150, 200, 250, 300, 350, 400];

export default function RatingBandsPage() {
  const [bandSize, setBandSize] = useState(100);
  const normalizedBandSize = useMemo(
    () => (ALLOWED_BAND_SIZES.includes(bandSize) ? bandSize : 100),
    [bandSize],
  );

  return (
    <div className="stack">
      <label>
        Band size
        <select value={normalizedBandSize} onChange={(e) => setBandSize(Number(e.target.value))}>
          {ALLOWED_BAND_SIZES.map((size) => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
      </label>
      <StatsTable
        title="Rating bands"
        description="Aggregated stats by white/black rating bands."
        queryKey={["rating-band-stats", String(normalizedBandSize)]}
        queryFn={() => listRatingBandStats(normalizedBandSize)}
      />
    </div>
  );
}
