import { getWebToken, setWebAuth } from "@/lib/auth";
import type {
  AnalysisProgressResponse,
  AnalysisRunResponse,
  AnalysisStatusResponse,
  GameDetail,
  GameOverview,
  OverviewSummary,
  SidelineCreateRequest,
  SidelineResponse,
  StatsRow,
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
  ReviewActionRequest,
  ReviewActionResponse,
  RuntimeSettings,
  RuntimeSettingsUpdateRequest,
  RepertoireImportResponse,
  RepertoireImportJobResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token";
const MAX_CONSECUTIVE_401S = 2;

let consecutiveUnauthorizedCount = 0;

function currentToken(): string {
  const fromStorage = getWebToken();
  return fromStorage && fromStorage.trim() ? fromStorage : API_TOKEN;
}

export function getAuthDiagnostics() {
  const fromStorage = getWebToken();
  return {
    apiBaseUrl: API_BASE_URL,
    tokenSource: fromStorage && fromStorage.trim() ? "localStorage (cg_web_api_token)" : "NEXT_PUBLIC_API_TOKEN env",
    hasStoredToken: Boolean(fromStorage && fromStorage.trim()),
  };
}

function redirectToLoginForUnauthorized() {
  if (typeof window === "undefined") {
    return;
  }
  setWebAuth(null);
  const reason = consecutiveUnauthorizedCount >= MAX_CONSECUTIVE_401S ? "unauthorized_repeated" : "unauthorized";
  window.location.assign(`/login?reason=${reason}`);
}

function headers(extra: Record<string, string> = {}): HeadersInit {
  return {
    Authorization: `Bearer ${currentToken()}`,
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
      consecutiveUnauthorizedCount += 1;
      if (consecutiveUnauthorizedCount >= MAX_CONSECUTIVE_401S) {
        redirectToLoginForUnauthorized();
      }
      throw new Error(
        "Unauthorized: your bearer token is missing/invalid. Open /login and set a valid backend API token.",
      );
    }

    throw new Error(parsedDetail || text || `Request failed with status ${response.status}`);
  }
  consecutiveUnauthorizedCount = 0;
  return (await response.json()) as T;
}

export async function validateApiToken(): Promise<{ ok: true; detail: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/validate`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<{ ok: true; detail: string }>(response);
}

async function getStats(path: string): Promise<StatsRow[]> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<StatsRow[]>(response);
}

export async function listSidelines(limit = 20): Promise<SidelineResponse[]> {
  const response = await fetch(`${API_BASE_URL}/sidelines?limit=${limit}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<SidelineResponse[]>(response);
}

export async function getSideline(id: string): Promise<SidelineResponse> {
  const response = await fetch(`${API_BASE_URL}/sidelines/${id}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<SidelineResponse>(response);
}

export async function createSideline(payload: SidelineCreateRequest, idempotencyKey: string): Promise<SidelineResponse> {
  const response = await fetch(`${API_BASE_URL}/sidelines`, {
    method: "POST",
    headers: headers({ "Idempotency-Key": idempotencyKey }),
    body: JSON.stringify(payload),
  });
  return unwrap<SidelineResponse>(response);
}

export async function listGames(limit = 50, offset = 0): Promise<GameOverview[]> {
  const response = await fetch(`${API_BASE_URL}/games?limit=${limit}&offset=${offset}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<GameOverview[]>(response);
}

export async function getGame(gameId: number): Promise<GameDetail> {
  const response = await fetch(`${API_BASE_URL}/games/${gameId}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<GameDetail>(response);
}

export async function getOverviewSummary(): Promise<OverviewSummary> {
  const response = await fetch(`${API_BASE_URL}/overview/summary`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<OverviewSummary>(response);
}

export async function listLineStats(): Promise<StatsRow[]> {
  return getStats("/lines/stats");
}

export async function listTimeUsageStats(): Promise<StatsRow[]> {
  return getStats("/time-usage/stats");
}

export async function listRatingBandStats(bandSize = 100): Promise<StatsRow[]> {
  return getStats(`/rating-bands/stats?band_size=${bandSize}`);
}

export async function listInsights(): Promise<StatsRow[]> {
  return getStats("/insights");
}

export async function listReviewItems(): Promise<StatsRow[]> {
  return getStats("/review/items");
}

export async function getTreeExplorer(): Promise<TreeExplorerResponse> {
  const response = await fetch(`${API_BASE_URL}/tree/explorer`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeExplorerResponse>(response);
}

export async function getTrainerQueue(): Promise<TrainerQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/trainer/queue`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TrainerQueueResponse>(response);
}

export async function submitTrainerAnswer(payload: TrainerAnswerRequest): Promise<TrainerAnswerResult> {
  const response = await fetch(`${API_BASE_URL}/trainer/answer`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerAnswerResult>(response);
}


export async function getLineTreeBrowse(posId = 1, mySideOnly = true): Promise<TreeBrowseResponse> {
  const response = await fetch(`${API_BASE_URL}/lines/tree/browse?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeBrowseResponse>(response);
}

export async function getLineTreeCoverage(posId = 1, mySideOnly = true): Promise<TreeCoverageResponse> {
  const response = await fetch(`${API_BASE_URL}/lines/tree/coverage?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeCoverageResponse>(response);
}

export async function getLineTreeBranchMetrics(posId = 1, mySideOnly = true): Promise<TreeBranchMetricsResponse> {
  const response = await fetch(`${API_BASE_URL}/lines/tree/branch-metrics?pos_id=${posId}&my_side_only=${mySideOnly}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TreeBranchMetricsResponse>(response);
}


export async function createTrainerSession(payload: TrainerSessionCreateRequest): Promise<TrainerSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/trainer/sessions`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerSessionResponse>(response);
}

export async function submitTrainerSessionAnswer(sessionId: string, payload: TrainerSessionAnswerRequest): Promise<TrainerSessionAnswerResponse> {
  const response = await fetch(`${API_BASE_URL}/trainer/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerSessionAnswerResponse>(response);
}

export async function getTrainerQueueV2(mode: "learn" | "review" = "review"): Promise<TrainerQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/trainer/queue?mode=${mode}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<TrainerQueueResponse>(response);
}

export async function submitTrainerOutcome(payload: TrainerOutcomeRequest): Promise<TrainerOutcomeResponse> {
  const response = await fetch(`${API_BASE_URL}/trainer/outcomes`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerOutcomeResponse>(response);
}

export async function setTrainerPriorityOverride(payload: TrainerPriorityOverrideRequest): Promise<TrainerQueueResponse["items"][number]> {
  const response = await fetch(`${API_BASE_URL}/trainer/priority-override`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<TrainerQueueResponse["items"][number]>(response);
}

export async function listReviewActions(status: "pending" | "approved" | "disapproved" | "all" = "pending"): Promise<ReviewProposition[]> {
  const response = await fetch(`${API_BASE_URL}/review/actions?status=${status}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<ReviewProposition[]>(response);
}

export async function executeReviewAction(payload: ReviewActionRequest): Promise<ReviewActionResponse> {
  const response = await fetch(`${API_BASE_URL}/review/actions`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<ReviewActionResponse>(response);
}



export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const response = await fetch(`${API_BASE_URL}/settings/runtime`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<RuntimeSettings>(response);
}

export async function updateRuntimeSettings(payload: RuntimeSettingsUpdateRequest): Promise<RuntimeSettings> {
  const response = await fetch(`${API_BASE_URL}/settings/runtime`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return unwrap<RuntimeSettings>(response);
}

export async function runFullAnalysis(): Promise<AnalysisRunResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/run/full`, {
    method: "POST",
    headers: headers(),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runEngineOnlyAnalysis(): Promise<AnalysisRunResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/run/engine-only`, {
    method: "POST",
    headers: headers(),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runFetchGames(): Promise<AnalysisRunResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/run/fetch-games`, {
    method: "POST",
    headers: headers(),
  });
  return unwrap<AnalysisRunResponse>(response);
}

export async function runSmokeTest(): Promise<AnalysisRunResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/run/smoke-test`, {
    method: "POST",
    headers: headers(),
  });
  return unwrap<AnalysisRunResponse>(response);
}


export async function importRepertoire(file: File): Promise<RepertoireImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/repertoires/import`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${currentToken()}`,
    },
    body: formData,
  });
  return unwrap<RepertoireImportResponse>(response);
}

export async function getRepertoireImportJob(jobId: string): Promise<RepertoireImportJobResponse> {
  const response = await fetch(`${API_BASE_URL}/repertoires/import-jobs/${jobId}`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<RepertoireImportJobResponse>(response);
}

export async function getAnalysisStatus(): Promise<AnalysisStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/status`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<AnalysisStatusResponse>(response);
}

export async function getAnalysisProgress(): Promise<AnalysisProgressResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/progress`, {
    method: "GET",
    headers: headers(),
    cache: "no-store",
  });
  return unwrap<AnalysisProgressResponse>(response);
}
