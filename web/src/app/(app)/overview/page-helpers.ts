import type { AnalysisRunHistoryEntry } from "@/lib/types";

function formatRunType(value: string | null | undefined): string {
  if (!value) return "N/A";
  return value.replaceAll("-", " ");
}

export type RunAction = "full" | "engine" | "fetch" | "smoke";

export interface RunTimelineSummary {
  latestRun: AnalysisRunHistoryEntry | null;
  recentFinishedRun: AnalysisRunHistoryEntry | null;
}

export function actionForRunType(runType: string): RunAction {
  if (runType === "engine-only-analysis") return "engine";
  if (runType === "fetch-games") return "fetch";
  if (runType === "smoke-test") return "smoke";
  return "full";
}

export function runActionLabel(run: AnalysisRunHistoryEntry): string {
  return run.status === "failed" ? `Retry ${formatRunType(run.run_type)}` : `Run ${formatRunType(run.run_type)} again`;
}

export function formatRunTypeLabel(value: string | null | undefined): string {
  return formatRunType(value);
}

export function summarizeRunTimeline(runs: AnalysisRunHistoryEntry[] | null | undefined): RunTimelineSummary {
  const allRuns = runs ?? [];
  return {
    latestRun: allRuns[0] ?? null,
    recentFinishedRun: allRuns.find((run) => run.status !== "running") ?? null,
  };
}

export function canTriggerRunAction(run: AnalysisRunHistoryEntry, isRunning: boolean, mutationPending: boolean): boolean {
  if (isRunning || mutationPending) return false;
  return run.status !== "running";
}
