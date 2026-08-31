"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { actionForRunType, canTriggerRunAction, formatRunTypeLabel as formatRunType, runActionLabel, summarizeRunTimeline } from "./page-helpers";
import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineTable } from "@/components/sideline-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DenseControlRow, DetailPane, EmptyState } from "@/components/ui/page-patterns";
import { SectionHeader } from "@/components/ui/section-header";
import { BodyText, CaptionText, CardTitle, FieldLabel, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";
import { getAnalysisProgress, getAnalysisRuns, getAnalysisStatus, getOverviewSummary, runEngineOnlyAnalysis, runFetchGames, runFullAnalysis, runSmokeTest } from "@/lib/api-client";
 

function formatTs(value: string | null | undefined): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

const KPI_CONFIG = [
  ["Lines", "Tracked repertoire branches", "lines"],
  ["Manual priority", "Manually queued review items", "manual_priority"],
  ["Auto-priority", "Automatically surfaced branches", "auto_priority"],
  ["Games", "Imported games available for review", "games"],
  ["Matched", "Games matched to repertoire lines", "matched"],
  ["Fully compliant", "Games that stayed fully in-book", "fully_compliant"],
] as const;

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState<string>("");
  const { data, isLoading, error } = useQuery({ queryKey: ["overview-summary"], queryFn: getOverviewSummary });
  const { data: status } = useQuery({ queryKey: ["analysis-status"], queryFn: getAnalysisStatus });
  const { data: progress } = useQuery({ queryKey: ["analysis-progress"], queryFn: getAnalysisProgress });
  const { data: runs } = useQuery({ queryKey: ["analysis-runs", 10], queryFn: () => getAnalysisRuns(10) });
  const isRunning = status?.state === "running";

  const refreshStatus = () => {
    queryClient.invalidateQueries({ queryKey: ["analysis-status"] });
    queryClient.invalidateQueries({ queryKey: ["analysis-progress"] });
    queryClient.invalidateQueries({ queryKey: ["analysis-runs", 10] });
  };

  const runMutation = useMutation({
    mutationFn: async (action: "full" | "engine" | "fetch" | "smoke") => {
      if (action === "full") return runFullAnalysis();
      if (action === "engine") return runEngineOnlyAnalysis();
      if (action === "fetch") return runFetchGames();
      return runSmokeTest();
    },
    onSuccess: (result) => {
      setActionMessage(`Started ${formatRunType(result.run_type)} (${result.job_id.slice(0, 8)}…).`);
      refreshStatus();
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

  const completedRuns = runs?.runs?.filter((run) => run.status === "completed").length ?? 0;
  const failedRuns = runs?.runs?.filter((run) => run.status === "failed").length ?? 0;
  const { latestRun, recentFinishedRun } = summarizeRunTimeline(runs?.runs);

  const rightRail = (
    <>
      <DetailPane title="Analysis status" description="A compact operations summary for the currently active job and the last completed backend run.">
        <div className="grid gap-4">
          <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
            <FieldLabel as="span">Pipeline state</FieldLabel>
            <CardTitle className="mt-2">{status?.state ?? "unknown"}</CardTitle>
          </div>
          <div className="grid gap-3">
            <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
              <CaptionText>Active job</CaptionText>
              <BodyText className="mt-2">{status?.active_job_id ? `${status.active_job_id.slice(0, 8)}… (${formatRunType(status.active_run_type)})` : "No active job"}</BodyText>
            </div>
            <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
              <CaptionText>Last completed job</CaptionText>
              <BodyText className="mt-2">{status?.last_completed_job_id ? `${status.last_completed_job_id.slice(0, 8)}… (${formatRunType(status.last_run_type)})` : "No completed jobs yet"}</BodyText>
            </div>
          </div>
          {status?.last_error ? <BodyText className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 font-medium text-warning">Last failure: {status.last_error}</BodyText> : <MutedText>No recent pipeline errors reported.</MutedText>}
        </div>
      </DetailPane>

      <DetailPane title="Sideline workspace" description="Sideline-related content is grouped separately so queue review stays distinct from pipeline controls.">
        <MutedText>Use the table below to review async sideline jobs, prioritize follow-up work, and inspect generated branches once analysis completes.</MutedText>
      </DetailPane>
    </>
  );

  return (
    <PageContainer
      title="Overview"
      description="Monitor pipeline health, launch analysis runs, and keep sideline work grouped in one dashboard."
      rightRail={rightRail}
      rightRailClassName="xl:sticky xl:top-24"
    >
      <PageSection>
        <SectionHeader
          title="Operations dashboard"
          description="Track the current pipeline, kick off the next run, and review recent analysis activity without bouncing between pages."
          actions={<Button variant="ghost" onClick={refreshStatus}>Refresh status</Button>}
        />

        {error ? <BodyText className="font-medium text-danger">{String(error)}</BodyText> : null}

        <div className="grid gap-grid-gap">
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {KPI_CONFIG.map(([label, detail, key]) => (
              <DetailPane key={label} className="gap-3 bg-card">
                <CaptionText>{label}</CaptionText>
                {isLoading ? <MutedText>Loading…</MutedText> : <p className="text-page-title font-semibold tracking-tight text-foreground">{String(data?.[key] ?? "—")}</p>}
                <MutedText>{detail}</MutedText>
              </DetailPane>
            ))}
          </div>

          <DetailPane
            title="Primary actions"
            description="Use the main pipeline entry points here. Actions stay together so the current run context is always visible next to them."
          >
            <DenseControlRow className="items-stretch gap-3">
              <Button variant="primary" disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("full")}>Run full analysis</Button>
              <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("engine")}>Run engine-only</Button>
              <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("fetch")}>Fetch games</Button>
              <Button disabled={isRunning || runMutation.isPending} onClick={() => runMutation.mutate("smoke")}>Run smoke test</Button>
            </DenseControlRow>
            {actionMessage ? <Badge tone={actionMessage.includes("already running") ? "warning" : "success"}>{actionMessage}</Badge> : null}
          </DetailPane>

          <div className="grid gap-grid-gap lg:grid-cols-2">
            <DetailPane title="Progress panel" description="Read the current message, completion state, and recent throughput at a glance.">
              <div className="grid gap-4">
                <div className="grid gap-1">
                  <FieldLabel as="span">Current message</FieldLabel>
                  <BodyText>{String(progress?.progress?.message ?? "No progress reported yet.")}</BodyText>
                </div>
                {progressPercent !== null ? (
                  <div className="grid gap-2">
                    <div className="h-3 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }} />
                    </div>
                    <MutedText>{progressPercent}% complete · {Number(progress?.progress?.done ?? 0)} of {Number(progress?.progress?.total ?? 0)} steps</MutedText>
                  </div>
                ) : (
                  <MutedText>Progress details will appear when a run emits step counts.</MutedText>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                    <CaptionText>Completed runs</CaptionText>
                    <CardTitle className="mt-2">{completedRuns}</CardTitle>
                  </div>
                  <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                    <CaptionText>Failed runs</CaptionText>
                    <CardTitle className="mt-2">{failedRuns}</CardTitle>
                  </div>
                </div>
              </div>
            </DetailPane>

            <DetailPane title="Run timeline" description="Recent jobs are ordered as an operational timeline so you can spot interruptions, finishes, and follow-up work quickly.">
              <div className="mb-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                  <CaptionText>Current run</CaptionText>
                  <BodyText className="mt-2">{latestRun ? `${formatRunType(latestRun.run_type)} · ${latestRun.status}` : "No runs yet"}</BodyText>
                  {latestRun ? <MutedText>{formatTs(latestRun.started_at)}</MutedText> : null}
                </div>
                <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                  <CaptionText>Most recent finished run</CaptionText>
                  <BodyText className="mt-2">{recentFinishedRun ? `${formatRunType(recentFinishedRun.run_type)} · ${recentFinishedRun.status}` : "No finished runs yet"}</BodyText>
                  {recentFinishedRun?.finished_at ? <MutedText>{formatTs(recentFinishedRun.finished_at)}</MutedText> : null}
                </div>
              </div>
              {(runs?.runs.length ?? 0) === 0 ? (
                <EmptyState title="No analysis runs yet" description="Start a pipeline action to populate the timeline and monitor recent job history here." />
              ) : (
                <ul className="grid gap-3">
                  {(runs?.runs ?? []).map((run, index) => (
                    <li key={run.run_id} className="grid gap-3 rounded-xl border border-border/70 bg-card px-4 py-4 sm:grid-cols-[auto_1fr]">
                      <div className="flex items-start justify-center">
                        <div className={cn("mt-1 h-3 w-3 rounded-full", run.status === "completed" ? "bg-success" : run.status === "failed" ? "bg-danger" : "bg-primary")} />
                      </div>
                      <div className="grid gap-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <CardTitle className="text-base">{formatRunType(run.run_type)}</CardTitle>
                          <Badge variant="outline">{run.status}</Badge>
                          <CaptionText>Run #{(runs?.runs.length ?? 0) - index}</CaptionText>
                        </div>
                        <BodyText className="text-muted-foreground">Started {formatTs(run.started_at)}{run.finished_at ? ` · Finished ${formatTs(run.finished_at)}` : " · In progress"}</BodyText>
                        {run.error_reason ? <BodyText className="font-medium text-warning">Issue: {run.error_reason}</BodyText> : null}
                        <div className="pt-1">
                          <Button
                            variant={run.status === "failed" ? "secondary" : "outline"}
                            size="sm"
                            disabled={!canTriggerRunAction(run, isRunning, runMutation.isPending)}
                            onClick={() => runMutation.mutate(actionForRunType(run.run_type))}
                          >
                            {runActionLabel(run)}
                          </Button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </DetailPane>
          </div>
        </div>
      </PageSection>

      <PageSection>
        <SectionHeader title="Sideline jobs" description="Async sideline generation work is grouped below the operational dashboard so branch review remains easy to scan." />
        <SidelineTable />
      </PageSection>
    </PageContainer>
  );
}
