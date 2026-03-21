"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineTable } from "@/components/sideline-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DenseControlRow, DetailPane, EmptyState, KpiSummary } from "@/components/ui/page-patterns";
import { SectionHeader } from "@/components/ui/section-header";
import { BodyText, CaptionText, CardTitle, FieldLabel, MutedText } from "@/components/ui/typography";
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
        {isLoading ? <MutedText>Loading summary…</MutedText> : null}
        {error ? <BodyText className="font-medium text-danger">{String(error)}</BodyText> : null}
        {data ? <KpiSummary><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[["Lines", data.lines],["Manual priority", data.manual_priority],["Auto-priority", data.auto_priority],["Games", data.games],["Matched", data.matched],["Fully compliant", data.fully_compliant]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-border/70 bg-card px-4 py-4"><CaptionText>{String(label)}</CaptionText><p className="mt-2 text-page-title font-semibold tracking-tight text-foreground">{String(value)}</p></div>)}</div></KpiSummary> : null}
        <DetailPane title="Analysis actions" description="Launch a new run, trigger fetches, or refresh the current status snapshot.">
          <DenseControlRow>
            <Button variant="primary" disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("full")}>Run full analysis</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("engine")}>Run engine-only</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("fetch")}>Fetch games</Button>
            <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("smoke")}>Run smoke test</Button>
            <Button variant="ghost" onClick={() => { queryClient.invalidateQueries({ queryKey: ["analysis-status"] }); queryClient.invalidateQueries({ queryKey: ["analysis-progress"] }); queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] }); }}>Refresh status</Button>
          </DenseControlRow>
          {actionMessage ? <Badge tone={actionMessage.includes("already running") ? "warning" : "success"}>{actionMessage}</Badge> : null}
        </DetailPane>
        <div className="grid gap-grid-gap xl:grid-cols-2">
          <DetailPane title="Job status">
            <div className="grid gap-4">
              <div className="grid gap-1"><FieldLabel as="span">State</FieldLabel><CardTitle>{status?.state ?? "unknown"}</CardTitle></div>
              <div className="grid gap-1"><FieldLabel as="span">Active job</FieldLabel><BodyText>{status?.active_job_id ? `${status.active_job_id.slice(0, 8)}… (${formatRunType(status.active_run_type)})` : "None"}</BodyText></div>
              <div className="grid gap-1"><FieldLabel as="span">Last job</FieldLabel><BodyText>{status?.last_completed_job_id ? `${status.last_completed_job_id.slice(0, 8)}… (${formatRunType(status.last_run_type)})` : "None"}</BodyText></div>
              {status?.last_error ? <BodyText className="font-medium text-warning">Last failure: {status.last_error}</BodyText> : null}
            </div>
          </DetailPane>
          <DetailPane title="Progress">
            <div className="grid gap-control-gap">
              <BodyText>{String(progress?.progress?.message ?? "No progress yet")}</BodyText>
              {progressPercent !== null ? <div className="grid gap-sm"><progress className="w-full" max={100} value={Math.max(0, Math.min(100, progressPercent))} /><MutedText>{progressPercent}% complete</MutedText></div> : null}
            </div>
          </DetailPane>
        </div>
        <DetailPane title="Run timeline" description="Recent analysis runs, timestamps, and failure reasons if any.">
          {(runs?.runs.length ?? 0) === 0 ? <EmptyState title="No analysis runs yet" description="Start a job to populate the timeline and monitor pipeline history from this page." /> : null}
          {(runs?.runs.length ?? 0) > 0 ? <ul className="grid gap-3">{(runs?.runs ?? []).map((run) => <li key={run.run_id} className="rounded-xl border border-border/70 bg-card px-4 py-4"><CaptionText>{formatRunType(run.run_type)}</CaptionText><BodyText className="mt-2 leading-7 text-muted-foreground">{run.status} · started {formatTs(run.started_at)}{run.finished_at ? ` · finished ${formatTs(run.finished_at)}` : ""}{run.error_reason ? ` · error: ${run.error_reason}` : ""}</BodyText></li>)}</ul> : null}
        </DetailPane>
      </PageSection>
      <PageSection>
        <SidelineTable />
      </PageSection>
    </PageContainer>
  );
}
