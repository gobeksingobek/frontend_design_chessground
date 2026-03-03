import { getWebToken } from "@/lib/auth";
import type {
  GameDetail,
  GameOverview,
  OverviewSummary,
  SidelineCreateRequest,
  SidelineResponse,
  StatsRow,
  TrainerAnswerRequest,
  TrainerAnswerResult,
  TrainerQueueResponse,
  TreeExplorerResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token";

function currentToken(): string {
  const fromStorage = getWebToken();
  return fromStorage && fromStorage.trim() ? fromStorage : API_TOKEN;
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
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
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
