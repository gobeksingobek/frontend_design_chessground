"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { StatsRow } from "@/lib/types";

export function StatsTable({
  title,
  description,
  queryKey,
  queryFn,
}: {
  title: string;
  description: string;
  queryKey: string[];
  queryFn: () => Promise<StatsRow[]>;
}) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });

  const columns = useMemo(() => {
    if (!data || data.length === 0) return [] as string[];
    return Object.keys(data[0] ?? {});
  }, [data]);

  return (
    <div className="stack">
      <h2>{title}</h2>
      <p>{description}</p>
      {isLoading ? <p>Loading…</p> : null}
      {error ? <p className="warn">{String(error)}</p> : null}
      {!isLoading && !error && (data?.length ?? 0) === 0 ? <p>No data yet.</p> : null}
      {!isLoading && !error && (data?.length ?? 0) > 0 ? (
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
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{String(row[column] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
