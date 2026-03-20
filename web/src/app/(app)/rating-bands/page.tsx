"use client";

import { useMemo, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { StatsTable } from "@/components/stats/stats-table";
import { Select } from "@/components/ui/select";
import { listRatingBandStats } from "@/lib/api-client";

const ALLOWED_BAND_SIZES = [50, 100, 150, 200, 250, 300, 350, 400];

export default function RatingBandsPage() {
  const [bandSize, setBandSize] = useState(100);
  const normalizedBandSize = useMemo(() => (ALLOWED_BAND_SIZES.includes(bandSize) ? bandSize : 100), [bandSize]);
  return <PageContainer title="Rating Bands" description="Compare performance by rating segments and adjust the resolution of the report."><PageSection><label className="grid max-w-xs gap-2 rounded-2xl border border-border bg-panel px-4 py-4 text-sm text-text-subtle shadow-soft">Band size<Select value={normalizedBandSize} onChange={(e) => setBandSize(Number(e.target.value))}>{ALLOWED_BAND_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}</Select></label><StatsTable title="Rating bands" description="Aggregated stats by white/black rating bands." queryKey={["rating-band-stats", String(normalizedBandSize)]} queryFn={() => listRatingBandStats(normalizedBandSize)} /></PageSection></PageContainer>;
}
