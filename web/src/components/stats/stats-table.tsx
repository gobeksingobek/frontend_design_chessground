"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { FormField } from "@/components/ui/form-field";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import type { StatsRow } from "@/lib/types";
import { cn } from "@/lib/cn";

type StatsPayload = StatsRow[] | { buckets: StatsRow[] };
type PivotOption = { value: string; label: string };
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

export function StatsTable({
  title,
  description,
  queryKey,
  queryFn,
  drilldownLabel = "Selected row",
  pivotOptions,
  pivotValue,
  onPivotChange,
  columnModelsByPivot,
}: {
  title: string;
  description: string;
  queryKey: string[];
  queryFn: () => Promise<StatsPayload>;
  drilldownLabel?: string;
  pivotOptions?: PivotOption[];
  pivotValue?: string;
  onPivotChange?: (pivot: string) => void;
  columnModelsByPivot?: Record<string, string[]>;
}) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [pivotColumn, setPivotColumn] = useState<string>("");
  const rows = useMemo<StatsRow[]>(() => normalizeStatsRows(data), [data]);
  const columns = useMemo(
    () => resolveColumns(rows, pivotValue && columnModelsByPivot ? columnModelsByPivot[pivotValue] : undefined),
    [rows, pivotValue, columnModelsByPivot],
  );
  const selected = useMemo(() => (rows.length > 0 ? rows[Math.min(selectedIndex, rows.length - 1)] : null), [rows, selectedIndex]);
  const pivot = useMemo(() => (!pivotColumn || !columns.includes(pivotColumn) ? [] : summarizePivot(rows, pivotColumn)), [rows, pivotColumn, columns]);

  return (
    <div className="grid gap-section-gap">
      {isLoading ? <StatsTableLoading /> : null}
      {error ? <p className="text-sm text-danger">{String(error)}</p> : null}
      {!isLoading && !error && rows.length === 0 ? <EmptyState title={`No ${title.toLowerCase()} data yet`} description={description} /> : null}
      {!isLoading && !error && rows.length > 0 ? (
        <>
          <FilterPanel title={`${title} filters`} description="Adjust the pivot column to compare related clusters without losing access to the active row detail.">
            <DenseControlRow>
              {pivotOptions && pivotValue && onPivotChange ? (
                <FormField label="Pivot" helpText="Switch report pivots for side-by-side comparison." className="min-w-[220px]">
                  <Select aria-label="Pivot" value={pivotValue} onChange={(e) => onPivotChange(e.target.value)}>
                    {pivotOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </Select>
                </FormField>
              ) : null}
              <FormField label="Pivot column" helpText="Summarize the dataset by any visible table column." className="min-w-[220px]">
                <Select aria-label="Pivot column" value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}>
                  <option value="">None</option>
                  {columns.map((column) => <option key={column} value={column}>{column}</option>)}
                </Select>
              </FormField>
            </DenseControlRow>
          </FilterPanel>
          <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.65fr)_minmax(20rem,1fr)] xl:items-start">
            <TableContainer className="xl:h-full">
              <Table>
                <TableHead><tr>{columns.map((column) => <Th key={column}>{column}</Th>)}</tr></TableHead>
                <TableBody>
                  {rows.map((row, index) => (
                    <TableRow key={index} className={cn("cursor-pointer hover:bg-hover", selectedIndex === index && "bg-selection text-selection-foreground")} onClick={() => setSelectedIndex(index)}>
                      {columns.map((column) => <Td key={column} className={selectedIndex === index ? "text-selection-foreground" : undefined}>{String(row[column] ?? "")}</Td>)}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <div className="grid gap-grid-gap">
              <DetailPane title={drilldownLabel} description="Inspect the selected row without losing the table context.">
                {!selected ? <p className="text-sm text-muted-foreground">No row selected.</p> : null}
                {selected ? <ul className="grid gap-control-gap text-sm text-foreground">{columns.map((column) => <li key={column}><strong>{column}:</strong> {String(selected[column] ?? "")}</li>)}</ul> : null}
              </DetailPane>
              {pivotColumn ? <DetailPane title={`Pivot summary by ${pivotColumn}`} description="Most frequent values in the current result set."><ul className="grid gap-control-gap text-sm text-muted-foreground">{pivot.slice(0, 10).map((entry) => <li key={entry.key} className="flex items-center justify-between gap-4 rounded-lg border border-border/60 bg-card px-3 py-2"><span className="truncate">{entry.key}</span><span className="font-medium text-foreground">{entry.count}</span></li>)}</ul></DetailPane> : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function StatsTableLoading() {
  return <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.65fr)_minmax(20rem,1fr)]"><Skeleton className="min-h-[24rem] w-full rounded-xl" /><Skeleton className="min-h-[24rem] w-full rounded-xl" /></div>;
}
