import type {
  AnalysisProgressResponse,
  AnalysisRunHistoryResponse,
  AnalysisRunResponse,
  AnalysisStatusResponse,
  GameDetail,
  GameOverview,
  OverviewSummary,
  PositionIntelligenceResponse,
  SidelineCreateRequest,
  SidelineResponse,
  StatsRow,
  InsightRow,
  TrainerAnswerRequest,
  TrainerAnswerResult,
  TrainerSessionAnswerRequest,
  TrainerSessionAnswerResponse,
  TrainerSessionCreateRequest,
  TrainerSessionResponse,
  TrainerOutcomeRequest,
  TrainerOutcomeResponse,
  TrainerPriorityOverrideRequest,
  TrainerQueueResponse,
  TreeBranchMetricsResponse,
  TreeBrowseResponse,
  TreeCoverageResponse,
  TreeExplorerResponse,
  ReviewProposition,
  ReviewPropositionDetail,
  ReviewActionRequest,
  ReviewActionResponse,
  BranchQueueEntry,
  RuntimeSettings,
  TimeUsagePivot,
  TimeUsageStatsResponse,
  RatingBandStatsResponse,
  RuntimeSettingsUpdateRequest,
  RepertoireImportResponse,
  RepertoireImportJobResponse,
  DurableJob,
} from "@/lib/types";

const API_BASE_URL = "/api/backend";

function headers(extra: Record<string, string> = {}): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...extra,
  };
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    let parsedDetail = "";

    try {
      const parsed = JSON.parse(text) as { detail?: { detail?: string; error_code?: string } };
      parsedDetail = parsed.detail?.detail ?? "";
    } catch {
      parsedDetail = "";
    }

    if (response.status === 401) {
      throw new Error(
        "The web service could not authenticate with the ChessGround backend. Check its server-side API_AUTH_TOKEN configuration.",
      );
    }

    throw new Error(parsedDetail || text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

async function getStats<T = StatsRow>(path: string): Promise<T[]> {
  const response = await apiFetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<T[]>(response);
}

export async function listSidelines(limit = 20): Promise<SidelineResponse[]> {
  const response = await apiFetch(`${API_BASE_URL}/sidelines?limit=${limit}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<SidelineResponse[]>(response);
}

export async function getSideline(id: string): Promise<SidelineResponse> {
  const response = await apiFetch(`${API_BASE_URL}/sidelines/${id}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<SidelineResponse>(response);
}

export async function createSideline(payload: SidelineCreateRequest, idempotencyKey: string): Promise<SidelineResponse> {
  const response = await apiFetch(`${API_BASE_URL}/sidelines`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": idempotencyKey }),
    body: JSON.stringify(payload),
  });
  return unwrap<SidelineResponse>(response);
}

export async function listGames(limit = 50, offset = 0): Promise<GameOverview[]> {
  const response = await apiFetch(`${API_BASE_URL}/games?limit=${limit}&offset=${offset}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<GameOverview[]>(response);
}

export interface ListGamesParams {
  limit?: number;
  offset?: number;
  result?: string;
  compliance?: string;
  complianceMin?: string;
  lineId?: string;
  player?: string;
  dateFrom?: string;
  dateTo?: string;
  sortBy?: "date" | "result" | "compliance" | "id";
  sortDir?: "asc" | "desc";
}

export async function listGamesFiltered(params: ListGamesParams = {}): Promise<GameOverview[]> {
  const search = new URLSearchParams();
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  if (params.result) search.set("result", params.result);
  if (params.compliance) search.set("compliance", params.compliance);
  if (params.complianceMin) search.set("compliance_min", params.complianceMin);
  if (params.lineId) search.set("line_id", params.lineId);
  if (params.player) search.set("player", params.player);
  if (params.dateFrom) search.set("date_from", params.dateFrom);
  if (params.dateTo) search.set("date_to", params.dateTo);
  if (params.sortBy) search.set("sort_by", params.sortBy);
  if (params.sortDir) search.set("sort_dir", params.sortDir);

  const response = await apiFetch(`${API_BASE_URL}/games?${search.toString()}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<GameOverview[]>(response);
}

export async function getGame(gameId: number): Promise<GameDetail> {
  const response = await apiFetch(`${API_BASE_URL}/games/${gameId}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<GameDetail>(response);
}

export async function getOverviewSummary(): Promise<OverviewSummary> {
  const response = await apiFetch(`${API_BASE_URL}/overview/summary`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<OverviewSummary>(response);
}

export async function listLineStats(): Promise<StatsRow[]> {
  return getStats("/lines/stats");
}

export async function getLineStatsDetail(lineId: string): Promise<StatsRow> {
  const response = await apiFetch(`${API_BASE_URL}/lines/stats/${encodeURIComponent(lineId)}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<StatsRow>(response);
}

export async function getLineStatsHistory(lineId: string): Promise<{ line_id: string; buckets: StatsRow[]; totals: Record<string, number> }> {
  const response = await apiFetch(`${API_BASE_URL}/lines/stats/${encodeURIComponent(lineId)}/history`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<{ line_id: string; buckets: StatsRow[]; totals: Record<string, number> }>(response);
}

export async function listTimeUsageStats(pivot: TimeUsagePivot): Promise<TimeUsageStatsResponse> {
  const response = await apiFetch(`${API_BASE_URL}/time-usage/stats?pivot=${pivot}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TimeUsageStatsResponse>(response);
}

export async function listRatingBandStats(bandSize = 100): Promise<RatingBandStatsResponse> {
  const response = await apiFetch(`${API_BASE_URL}/rating-bands/stats?band_size=${bandSize}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<RatingBandStatsResponse>(response);
}

export async function listInsights(): Promise<InsightRow[]> {
  return getStats("/insights");
}

export async function listReviewItems(): Promise<StatsRow[]> {
  return getStats("/review/items");
}

export async function getTreeExplorer(): Promise<TreeExplorerResponse> {
  const response = await apiFetch(`${API_BASE_URL}/tree/explorer`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeExplorerResponse>(response);
}

export async function getTrainerQueue(): Promise<TrainerQueueResponse> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/queue`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TrainerQueueResponse>(response);
}

export async function submitTrainerAnswer(payload: TrainerAnswerRequest): Promise<TrainerAnswerResult> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/answer`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerAnswerResult>(response);
}


export async function getLineTreeBrowse(posId = 1, mySideOnly = true): Promise<TreeBrowseResponse> {
  const response = await apiFetch(`${API_BASE_URL}/lines/tree/browse?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeBrowseResponse>(response);
}

export async function getLineTreeCoverage(posId = 1, mySideOnly = true): Promise<TreeCoverageResponse> {
  const response = await apiFetch(`${API_BASE_URL}/lines/tree/coverage?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeCoverageResponse>(response);
}

export async function getLineTreeBranchMetrics(posId = 1, mySideOnly = true): Promise<TreeBranchMetricsResponse> {
  const response = await apiFetch(`${API_BASE_URL}/lines/tree/branch-metrics?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeBranchMetricsResponse>(response);
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    const detail = error instanceof Error && error.message ? ` (${error.message})` : "";
    throw new Error(
      `Unable to reach the ChessGround API proxy at ${API_BASE_URL}.${detail}`,
    );
  }
}

export async function getPositionIntelligence(posId = 1, mySideOnly = true): Promise<PositionIntelligenceResponse> {
  const response = await apiFetch(`${API_BASE_URL}/positions/${posId}/intelligence?my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<PositionIntelligenceResponse>(response);
}


export async function createTrainerSession(payload: TrainerSessionCreateRequest): Promise<TrainerSessionResponse> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/sessions`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerSessionResponse>(response);
}

export async function submitTrainerSessionAnswer(sessionId: string, payload: TrainerSessionAnswerRequest): Promise<TrainerSessionAnswerResponse> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerSessionAnswerResponse>(response);
}

export async function getTrainerQueueV2(mode: "learn" | "review" = "review"): Promise<TrainerQueueResponse> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/queue?mode=${mode}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TrainerQueueResponse>(response);
}

export async function submitTrainerOutcome(payload: TrainerOutcomeRequest): Promise<TrainerOutcomeResponse> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/outcomes`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerOutcomeResponse>(response);
}

export async function setTrainerPriorityOverride(payload: TrainerPriorityOverrideRequest): Promise<TrainerQueueResponse["items"][number]> {
  const response = await apiFetch(`${API_BASE_URL}/trainer/priority-override`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerQueueResponse["items"][number]>(response);
}

export async function listReviewActions(status: "pending" | "approved" | "disapproved" | "all" = "pending"): Promise<ReviewProposition[]> {
  const response = await apiFetch(`${API_BASE_URL}/review/actions?status=${status}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<ReviewProposition[]>(response);
}

export async function getReviewAction(propositionId: number): Promise<ReviewPropositionDetail> {
  const response = await apiFetch(`${API_BASE_URL}/review/actions/${propositionId}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<ReviewPropositionDetail>(response);
}

export async function listReviewBranchQueue(): Promise<BranchQueueEntry[]> {
  const response = await apiFetch(`${API_BASE_URL}/review/branch-queue`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<BranchQueueEntry[]>(response);
}

export async function executeReviewAction(payload: ReviewActionRequest): Promise<ReviewActionResponse> {
  const response = await apiFetch(`${API_BASE_URL}/review/actions`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<ReviewActionResponse>(response);
}



export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const response = await apiFetch(`${API_BASE_URL}/settings/runtime`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<RuntimeSettings>(response);
}

export async function updateRuntimeSettings(payload: RuntimeSettingsUpdateRequest): Promise<RuntimeSettings> {
  const response = await apiFetch(`${API_BASE_URL}/settings/runtime`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<RuntimeSettings>(response);
}

export async function runFullAnalysis(): Promise<AnalysisRunResponse> {
  const response = await apiFetch(`${API_BASE_URL}/analysis/run/full`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": crypto.randomUUID() }),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runEngineOnlyAnalysis(): Promise<AnalysisRunResponse> {
  const response = await apiFetch(`${API_BASE_URL}/analysis/run/engine-only`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": crypto.randomUUID() }),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runFetchGames(): Promise<AnalysisRunResponse> {
  const response = await apiFetch(`${API_BASE_URL}/analysis/run/fetch-games`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": crypto.randomUUID() }),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runSmokeTest(): Promise<AnalysisRunResponse> {
  const response = await apiFetch(`${API_BASE_URL}/analysis/run/smoke-test`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": crypto.randomUUID() }),
  });
  return unwrap<AnalysisRunResponse>(response);
}


export async function importRepertoire(file: File): Promise<RepertoireImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(`${API_BASE_URL}/repertoires/import`, {
    method: "POST",
    headers: {
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: formData,
  });
  return unwrap<RepertoireImportResponse>(response);
}

export async function getRepertoireImportJob(jobId: string): Promise<RepertoireImportJobResponse> {
  const job = await getJob(jobId);
  return {
    id: job.job_id,
    status: job.status,
    progress: { ...job.progress, ...(job.result ?? {}) },
  };
}

export async function getJob(jobId: string): Promise<DurableJob> {
  const response = await apiFetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<DurableJob>(response);
}

export async function listJobs(limit = 20): Promise<DurableJob[]> {
  const response = await apiFetch(`${API_BASE_URL}/jobs?limit=${limit}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<DurableJob[]>(response);
}

function isAnalysisJob(job: DurableJob): boolean {
  return job.job_type.includes("analysis") || job.job_type.includes("reanalysis");
}

export async function getAnalysisStatus(): Promise<AnalysisStatusResponse> {
  const rows = (await listJobs(50)).filter(isAnalysisJob);
  const active = rows.find((job) => ["queued", "running", "retry"].includes(job.status));
  const latest = rows[0];
  const completed = rows.find((job) => job.status === "completed");
  const state = active ? "running" : latest?.status === "failed" || latest?.status === "cancelled"
    ? "failed" : latest?.status === "completed" ? "completed" : "idle";
  return {
    state,
    active_job_id: active?.job_id ?? null,
    active_run_type: active?.job_type ?? null,
    last_completed_job_id: completed?.job_id ?? null,
    last_run_type: latest?.job_type ?? null,
    last_error: latest?.error_detail ?? null,
    updated_at: latest?.updated_at ?? new Date().toISOString(),
  };
}

export async function getAnalysisProgress(): Promise<AnalysisProgressResponse> {
  const latest = (await listJobs(50)).find(isAnalysisJob);
  return {
    job_id: latest?.job_id ?? null,
    run_type: latest?.job_type ?? null,
    progress: latest?.progress ?? null,
    updated_at: latest?.updated_at ?? new Date().toISOString(),
  };
}

export async function getAnalysisRuns(limit = 10): Promise<AnalysisRunHistoryResponse> {
  const rows = (await listJobs(Math.min(Math.max(limit * 3, 10), 100))).filter(isAnalysisJob);
  return {
    runs: rows.slice(0, limit).map((job) => ({
      run_id: job.job_id,
      run_type: job.job_type,
      status: job.status === "completed" ? "completed" : ["failed", "cancelled"].includes(job.status) ? "failed" : "running",
      started_at: job.started_at ?? job.queued_at,
      finished_at: job.finished_at,
      error_reason: job.error_detail,
    })),
  };
}
