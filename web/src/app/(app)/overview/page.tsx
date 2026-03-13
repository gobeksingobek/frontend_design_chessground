"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SidelineTable } from "@/components/sideline-table";
import {
  getAnalysisProgress,
  getAnalysisRuns,
  getAnalysisStatus,
  getOverviewSummary,
  runEngineOnlyAnalysis,
  runFetchGames,
  runFullAnalysis,
  runSmokeTest,
} from "@/lib/api-client";

function formatRunType(value: string | null | undefined): string {
  if (!value) return "N/A";
  return value.replaceAll("-", " ");
}

function formatTs(value: string | null | undefined): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState<string>("");

  const { data, isLoading, error } = useQuery({ queryKey: ["overview-summary"], queryFn: getOverviewSummary });
  const { data: status } = useQuery({
    queryKey: ["analysis-status"],
    queryFn: getAnalysisStatus,
    refetchInterval: 2000,
  });
  const { data: progress } = useQuery({
    queryKey: ["analysis-progress"],
    queryFn: getAnalysisProgress,
    refetchInterval: 2000,
  });
  const { data: runs } = useQuery({
    queryKey: ["analysis-runs", 10],
    queryFn: () => getAnalysisRuns(10),
    refetchInterval: 2000,
  });

  const isRunning = status?.state === "running";

  const runMutation = useMutation({
    mutationFn: async (action: "full" | "engine" | "fetch" | "smoke") => {
      if (action === "full") return runFullAnalysis();
      if (action === "engine") return runEngineOnlyAnalysis();
      if (action === "fetch") return runFetchGames();
      return runSmokeTest();
    },
    onSuccess: (result) => {
      setActionMessage(`Started ${formatRunType(result.run_type)} (${result.job_id.slice(0, 8)}…).`);
      queryClient.invalidateQueries({ queryKey: ["analysis-status"] });
      queryClient.invalidateQueries({ queryKey: ["analysis-progress"] });
      queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] });
    },
    onError: (err) => {
      setActionMessage((err as Error).message);
    },
  });

  const progressPercent = useMemo(() => {
    const done = Number(progress?.progress?.done ?? 0);
    const total = Number(progress?.progress?.total ?? 0);
    if (!total || Number.isNaN(done) || Number.isNaN(total)) return null;
    return Math.round((done / total) * 100);
  }, [progress]);

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

      <div className="card">
        <h3>Analysis actions</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("full")}>Run full analysis</button>
          <button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("engine")}>Run engine-only</button>
          <button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("fetch")}>Fetch games</button>
          <button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("smoke")}>Run smoke test</button>
          <button onClick={() => {
            queryClient.invalidateQueries({ queryKey: ["analysis-status"] });
            queryClient.invalidateQueries({ queryKey: ["analysis-progress"] });
            queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] });
          }}>Refresh status</button>
        </div>
        {actionMessage ? <p className={actionMessage.includes("already running") ? "warn" : "ok"}>{actionMessage}</p> : null}
      </div>

      <div className="card">
        <h3>Job status</h3>
        <p>State: <strong>{status?.state ?? "unknown"}</strong></p>
        <p>Active job: {status?.active_job_id ? `${status.active_job_id.slice(0, 8)}… (${formatRunType(status.active_run_type)})` : "None"}</p>
        <p>Last job: {status?.last_completed_job_id ? `${status.last_completed_job_id.slice(0, 8)}… (${formatRunType(status.last_run_type)})` : "None"}</p>
        {status?.last_error ? <p className="warn">Last failure: {status.last_error}</p> : null}
      </div>

      <div className="card">
        <h3>Run timeline</h3>
        {(runs?.runs.length ?? 0) === 0 ? <p>No analysis runs yet.</p> : null}
        <ul>
          {(runs?.runs ?? []).map((run) => (
            <li key={run.run_id}>
              <strong>{formatRunType(run.run_type)}</strong> · {run.status} · started {formatTs(run.started_at)}
              {run.finished_at ? ` · finished ${formatTs(run.finished_at)}` : ""}
              {run.error_reason ? ` · error: ${run.error_reason}` : ""}
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Progress</h3>
        <p>{String(progress?.progress?.message ?? "No progress yet")}</p>
        {progressPercent !== null ? (
          <>
            <progress max={100} value={Math.max(0, Math.min(100, progressPercent))} />
            <small>{progressPercent}%</small>
          </>
        ) : null}
      </div>

      <SidelineTable />
    </div>
  );
}
