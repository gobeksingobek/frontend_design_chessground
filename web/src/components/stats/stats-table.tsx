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

export function StatsTable({ title, description, queryKey, queryFn, drilldownLabel = "Selected row" }: { title: string; description: string; queryKey: string[]; queryFn: () => Promise<StatsPayload>; drilldownLabel?: string; }) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [pivotColumn, setPivotColumn] = useState<string>("");
  const rows = useMemo<StatsRow[]>(() => normalizeStatsRows(data), [data]);
  const columns = useMemo(() => (rows.length === 0 ? [] as string[] : Object.keys(rows[0] ?? {})), [rows]);
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
