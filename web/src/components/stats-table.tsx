"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { StatsRow } from "@/lib/types";

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
  queryFn: () => Promise<StatsRow[]>;
  drilldownLabel?: string;
}) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [pivotColumn, setPivotColumn] = useState<string>("");

  const columns = useMemo(() => {
    if (!data || data.length === 0) return [] as string[];
    return Object.keys(data[0] ?? {});
  }, [data]);

  const selected = useMemo(() => (data && data.length > 0 ? data[Math.min(selectedIndex, data.length - 1)] : null), [data, selectedIndex]);

  const pivot = useMemo(() => {
    if (!data || !pivotColumn || !columns.includes(pivotColumn)) return [] as Array<{ key: string; count: number }>;
    const counts = new Map<string, number>();
    for (const row of data) {
      const key = String(row[pivotColumn] ?? "(empty)");
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries()).map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
  }, [data, pivotColumn, columns]);

  return (
    <div className="stack">
      <h2>{title}</h2>
      <p>{description}</p>
      {isLoading ? <p>Loading…</p> : null}
      {error ? <p className="warn">{String(error)}</p> : null}
      {!isLoading && !error && (data?.length ?? 0) === 0 ? <p>No data yet.</p> : null}
      {!isLoading && !error && (data?.length ?? 0) > 0 ? (
        <>
          <div className="card" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label>
              Pivot column
              <select value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}>
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
              {(data ?? []).map((row, index) => (
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
