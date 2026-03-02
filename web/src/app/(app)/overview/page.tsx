"use client";

import { useQuery } from "@tanstack/react-query";

import { SidelineTable } from "@/components/sideline-table";
import { getOverviewSummary } from "@/lib/api-client";

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["overview-summary"], queryFn: getOverviewSummary });

  return (
    <div className="stack">
      <h2>Overview</h2>
      {isLoading ? <p>Loading summary…</p> : null}
      {error ? <p className="warn">{String(error)}</p> : null}
      {data ? (
        <div className="card">
          <strong>
            Lines: {data.lines} | Manual priority: {data.manual_priority} | Auto-priority: {data.auto_priority} | Games: {data.games} |
            Matched: {data.matched} | Fully compliant: {data.fully_compliant}
          </strong>
        </div>
      ) : null}
      <SidelineTable />
    </div>
  );
}
