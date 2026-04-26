import type { StatsRow } from "@/lib/types";

export type StatsPayload = StatsRow[] | { buckets: StatsRow[] };

export type RatingBandGuardrails = {
  min: number;
  max: number;
  step: number;
  allowedBandSizes: number[];
  fallback: number;
};

export type RatingBandMetadata = {
  band_size?: number;
  allowed_band_sizes?: number[];
  percentiles?: Record<string, number | null>;
  totals?: Record<string, number>;
};

type DetailTab = "detail" | "history";
export type { DetailTab };

export function normalizeBandSizeByGuardrails(bandSize: number, guardrails: RatingBandGuardrails): number {
  const candidate = Number.isFinite(bandSize) ? Math.floor(bandSize) : guardrails.fallback;
  if (candidate < guardrails.min || candidate > guardrails.max) return guardrails.fallback;
  if ((candidate - guardrails.min) % guardrails.step !== 0) return guardrails.fallback;
  if (!guardrails.allowedBandSizes.includes(candidate)) return guardrails.fallback;
  return candidate;
}

export function buildRatingBandSummary(metadata: RatingBandMetadata | undefined): Array<{ label: string; value: string }> {
  if (!metadata) return [];
  const totals = metadata.totals ?? {};
  const percentiles = metadata.percentiles ?? {};
  const p50 = percentiles.p50_compliance_rate;
  const p75 = percentiles.p75_compliance_rate;
  return [
    { label: "Band size", value: String(metadata.band_size ?? "—") },
    { label: "Total games", value: String(totals.total_games ?? 0) },
    { label: "Bucket count", value: String(totals.bucket_count ?? 0) },
    { label: "Median compliance", value: p50 == null ? "—" : `${(p50 * 100).toFixed(1)}%` },
    { label: "P75 compliance", value: p75 == null ? "—" : `${(p75 * 100).toFixed(1)}%` },
  ];
}

export function resolveColumns(rows: StatsRow[], columnModel: string[] | undefined): string[] {
  if (rows.length === 0) return [];
  const allColumns = Object.keys(rows[0] ?? {});
  if (!columnModel || columnModel.length === 0) return allColumns;
  return columnModel.filter((column) => allColumns.includes(column));
}

export function normalizeStatsRows(data: StatsPayload | undefined): StatsRow[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return (data.buckets as StatsRow[]) ?? [];
}

export function summarizePivot(rows: StatsRow[], pivotColumn: string): Array<{ key: string; count: number }> {
  if (!pivotColumn) return [];
  const counts = new Map<string, number>();
  for (const row of rows) {
    const key = String(row[pivotColumn] ?? "(empty)");
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from(counts.entries()).map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
}

export function resolveSelectedRowIndex(selectedIndex: number, rowCount: number): number {
  if (rowCount <= 0) return 0;
  return Math.min(Math.max(0, selectedIndex), rowCount - 1);
}

export function resolveSelectedRowId(selected: StatsRow | null, rowIdField: string | undefined): string | null {
  if (!selected || !rowIdField) return null;
  const candidate = selected[rowIdField];
  if (candidate == null) return null;
  return String(candidate);
}

export function resolveDetailTab(nextTab: string, hasHistoryTab: boolean): DetailTab {
  if (nextTab === "history" && hasHistoryTab) return "history";
  return "detail";
}
