"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineTable } from "@/components/sideline-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";
import { getAnalysisProgress, getAnalysisRuns, getAnalysisStatus, getOverviewSummary, runEngineOnlyAnalysis, runFetchGames, runFullAnalysis, runSmokeTest } from "@/lib/api-client";

function formatRunType(value: string | null | undefined): string { if (!value) return "N/A"; return value.replaceAll("-", " "); }
function formatTs(value: string | null | undefined): string { if (!value) return "N/A"; const date = new Date(value); if (Number.isNaN(date.getTime())) return value; return date.toLocaleString(); }

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState<string>("");
  const { data, isLoading, error } = useQuery({ queryKey: ["overview-summary"], queryFn: getOverviewSummary });
  const { data: status } = useQuery({ queryKey: ["analysis-status"], queryFn: getAnalysisStatus, refetchInterval: 2000 });
  const { data: progress } = useQuery({ queryKey: ["analysis-progress"], queryFn: getAnalysisProgress, refetchInterval: 2000 });
  const { data: runs } = useQuery({ queryKey: ["analysis-runs", 10], queryFn: () => getAnalysisRuns(10), refetchInterval: 2000 });
  const isRunning = status?.state === "running";
  const runMutation = useMutation({ mutationFn: async (action: "full" | "engine" | "fetch" | "smoke") => { if (action === "full") return runFullAnalysis(); if (action === "engine") return runEngineOnlyAnalysis(); if (action === "fetch") return runFetchGames(); return runSmokeTest(); }, onSuccess: (result) => { setActionMessage(`Started ${formatRunType(result.run_type)} (${result.job_id.slice(0, 8)}…).`); queryClient.invalidateQueries({ queryKey: ["analysis-status"] }); queryClient.invalidateQueries({ queryKey: ["analysis-progress"] }); queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] }); }, onError: (err) => { setActionMessage((err as Error).message); } });
  const progressPercent = useMemo(() => { const done = Number(progress?.progress?.done ?? 0); const total = Number(progress?.progress?.total ?? 0); if (!total || Number.isNaN(done) || Number.isNaN(total)) return null; return Math.round((done / total) * 100); }, [progress]);

  return (
    <PageContainer title="Overview" description="Monitor backend pipeline health, launch analysis jobs, and review recent progress.">
      <PageSection>
        <SectionHeader title="Overview" description="Status, runs, and quick analysis actions for the backend pipeline." />
        {isLoading ? <p className="text-sm text-text-muted">Loading summary…</p> : null}
        {error ? <p className="text-sm text-danger">{String(error)}</p> : null}
        {data ? <Card><div className="flex flex-wrap gap-2">{[["Lines", data.lines],["Manual priority", data.manual_priority],["Auto-priority", data.auto_priority],["Games", data.games],["Matched", data.matched],["Fully compliant", data.fully_compliant]].map(([label, value]) => <Badge key={String(label)} tone="accent">{label}: {value}</Badge>)}</div></Card> : null}
        <Card>
          <SectionHeader title="Analysis actions" />
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("full")}>Run full analysis</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("engine")}>Run engine-only</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("fetch")}>Fetch games</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("smoke")}>Run smoke test</Button>
            <Button variant="ghost" onClick={() => { queryClient.invalidateQueries({ queryKey: ["analysis-status"] }); queryClient.invalidateQueries({ queryKey: ["analysis-progress"] }); queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] }); }}>Refresh status</Button>
          </div>
          {actionMessage ? <Badge tone={actionMessage.includes("already running") ? "warning" : "success"}>{actionMessage}</Badge> : null}
        </Card>
        <Card><SectionHeader title="Job status" /><p>State: <strong>{status?.state ?? "unknown"}</strong></p><p>Active job: {status?.active_job_id ? `${status.active_job_id.slice(0, 8)}… (${formatRunType(status.active_run_type)})` : "None"}</p><p>Last job: {status?.last_completed_job_id ? `${status.last_completed_job_id.slice(0, 8)}… (${formatRunType(status.last_run_type)})` : "None"}</p>{status?.last_error ? <p className="text-sm text-warning">Last failure: {status.last_error}</p> : null}</Card>
        <Card><SectionHeader title="Run timeline" />{(runs?.runs.length ?? 0) === 0 ? <p className="text-sm text-text-muted">No analysis runs yet.</p> : null}<ul className="grid gap-2 text-sm text-text-subtle">{(runs?.runs ?? []).map((run) => <li key={run.run_id}><strong>{formatRunType(run.run_type)}</strong> · {run.status} · started {formatTs(run.started_at)}{run.finished_at ? ` · finished ${formatTs(run.finished_at)}` : ""}{run.error_reason ? ` · error: ${run.error_reason}` : ""}</li>)}</ul></Card>
        <Card><SectionHeader title="Progress" /><p>{String(progress?.progress?.message ?? "No progress yet")}</p>{progressPercent !== null ? <div className="grid gap-2"><progress className="w-full" max={100} value={Math.max(0, Math.min(100, progressPercent))} /><small className="text-text-muted">{progressPercent}%</small></div> : null}</Card>
      </PageSection>
      <PageSection>
        <SidelineTable />
      </PageSection>
    </PageContainer>
  );
}
