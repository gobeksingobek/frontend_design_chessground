"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { SectionHeader } from "@/components/ui/section-header";
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
    <div className="grid gap-4">
      <SectionHeader title={title} description={description} />
      {isLoading ? <p className="text-sm text-text-muted">Loading…</p> : null}
      {error ? <p className="text-sm text-danger">{String(error)}</p> : null}
      {!isLoading && !error && rows.length === 0 ? <p className="text-sm text-text-muted">No data yet.</p> : null}
      {!isLoading && !error && rows.length > 0 ? (
        <>
          <Card className="flex flex-wrap items-center gap-3">
            <label className="grid min-w-[220px] gap-2 text-sm text-text-subtle">Pivot column<Select aria-label="Pivot column" value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}><option value="">None</option>{columns.map((column) => <option key={column} value={column}>{column}</option>)}</Select></label>
          </Card>
          <Table>
            <TableHead><tr>{columns.map((column) => <Th key={column}>{column}</Th>)}</tr></TableHead>
            <TableBody>
              {rows.map((row, index) => (
                <tr key={index} className={cn("cursor-pointer transition hover:bg-panel-muted/70", selectedIndex === index && "bg-accent/10")} onClick={() => setSelectedIndex(index)}>
                  {columns.map((column) => <Td key={column}>{String(row[column] ?? "")}</Td>)}
                </tr>
              ))}
            </TableBody>
          </Table>
          <Card>
            <h3 className="text-base font-semibold">{drilldownLabel}</h3>
            {!selected ? <p className="text-sm text-text-muted">No row selected.</p> : null}
            {selected ? <ul className="grid gap-2 text-sm">{columns.map((column) => <li key={column}><strong>{column}:</strong> {String(selected[column] ?? "")}</li>)}</ul> : null}
            {pivotColumn ? <><h4 className="text-sm font-semibold text-text">Pivot summary by {pivotColumn}</h4><ul className="grid gap-2 text-sm text-text-subtle">{pivot.slice(0, 10).map((entry) => <li key={entry.key}>{entry.key}: {entry.count}</li>)}</ul></> : null}
          </Card>
        </>
      ) : null}
    </div>
  );
}
