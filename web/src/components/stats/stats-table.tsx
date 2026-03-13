"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { StatsRow } from "@/lib/types";

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


export function StatsTable({
  title,
  description,
  queryKey,
  queryFn,
  drilldownLabel = "Selected row",
}: {
  title: string;
  description: string;
  queryKey: string[];
  queryFn: () => Promise<StatsPayload>;
  drilldownLabel?: string;
}) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [pivotColumn, setPivotColumn] = useState<string>("");

  const rows = useMemo<StatsRow[]>(() => normalizeStatsRows(data), [data]);

  const columns = useMemo(() => {
    if (rows.length === 0) return [] as string[];
    return Object.keys(rows[0] ?? {});
  }, [rows]);

  const selected = useMemo(() => (rows.length > 0 ? rows[Math.min(selectedIndex, rows.length - 1)] : null), [rows, selectedIndex]);

  const pivot = useMemo(() => {
    if (!pivotColumn || !columns.includes(pivotColumn)) return [] as Array<{ key: string; count: number }>;
    return summarizePivot(rows, pivotColumn);
  }, [rows, pivotColumn, columns]);

  return (
    <div className="stack">
      <h2>{title}</h2>
      <p>{description}</p>
      {isLoading ? <p>Loading…</p> : null}
      {error ? <p className="warn">{String(error)}</p> : null}
      {!isLoading && !error && rows.length === 0 ? <p>No data yet.</p> : null}
      {!isLoading && !error && rows.length > 0 ? (
        <>
          <div className="card" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label>
              Pivot column
              <select aria-label="Pivot column" value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}>
                <option value="">None</option>
                {columns.map((column) => (
                  <option key={column} value={column}>{column}</option>
                ))}
              </select>
            </label>
          </div>
          <table className="table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className={selectedIndex === index ? "row-selected" : ""} onClick={() => setSelectedIndex(index)}>
                  {columns.map((column) => (
                    <td key={column}>{String(row[column] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          <div className="card">
            <h3>{drilldownLabel}</h3>
            {!selected ? <p>No row selected.</p> : null}
            {selected ? (
              <ul>
                {columns.map((column) => (
                  <li key={column}><strong>{column}:</strong> {String(selected[column] ?? "")}</li>
                ))}
              </ul>
            ) : null}
            {pivotColumn ? (
              <>
                <h4>Pivot summary by {pivotColumn}</h4>
                <ul>
                  {pivot.slice(0, 10).map((entry) => (
                    <li key={entry.key}>{entry.key}: {entry.count}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
