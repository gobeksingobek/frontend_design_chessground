"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/table";
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
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {error ? <p className="text-sm text-danger">{String(error)}</p> : null}
      {!isLoading && !error && rows.length === 0 ? <EmptyState title={`No ${title.toLowerCase()} data yet`} description={description} /> : null}
      {!isLoading && !error && rows.length > 0 ? (
        <>
          <FilterPanel title={`${title} filters`} description="Adjust the pivot while keeping dense controls compact.">
            <DenseControlRow>
              <label className="grid min-w-[220px] gap-xs text-sm text-muted-foreground">Pivot column<Select aria-label="Pivot column" value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}><option value="">None</option>{columns.map((column) => <option key={column} value={column}>{column}</option>)}</Select></label>
            </DenseControlRow>
          </FilterPanel>
          <Table>
            <TableHead><tr>{columns.map((column) => <Th key={column}>{column}</Th>)}</tr></TableHead>
            <TableBody>
              {rows.map((row, index) => (
                <tr key={index} className={cn("cursor-pointer transition hover:bg-hover", selectedIndex === index && "bg-selection text-selection-foreground")} onClick={() => setSelectedIndex(index)}>
                  {columns.map((column) => <Td key={column} className={selectedIndex === index ? "text-selection-foreground" : undefined}>{String(row[column] ?? "")}</Td>)}
                </tr>
              ))}
            </TableBody>
          </Table>
          <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
            <DetailPane title={drilldownLabel} description="Inspect the currently selected row in a more readable layout.">
              {!selected ? <p className="text-sm text-muted-foreground">No row selected.</p> : null}
              {selected ? <ul className="grid gap-control-gap text-sm text-foreground">{columns.map((column) => <li key={column}><strong>{column}:</strong> {String(selected[column] ?? "")}</li>)}</ul> : null}
            </DetailPane>
            {pivotColumn ? <DetailPane title={`Pivot summary by ${pivotColumn}`} description="Top values by row count for the selected pivot."><ul className="grid gap-control-gap text-sm text-muted-foreground">{pivot.slice(0, 10).map((entry) => <li key={entry.key}>{entry.key}: {entry.count}</li>)}</ul></DetailPane> : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
