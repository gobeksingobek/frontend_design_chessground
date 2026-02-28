import type { GameDetail, GameOverview, SidelineCreateRequest, SidelineResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token";

function headers(extra: Record<string, string> = {}): HeadersInit {
  return {
    Authorization: `Bearer ${API_TOKEN}`,
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
