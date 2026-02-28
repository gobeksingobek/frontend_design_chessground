export type SidelineStatus = "queued" | "processing" | "retry" | "failed" | "completed";

export interface SidelineResponse {
  id: string;
  game_id: string;
  move_ply: number;
  requested_by: string;
  status: SidelineStatus;
  idempotency_key: string;
  attempts: number;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SidelineCreateRequest {
  game_id: string;
  move_ply: number;
  fen: string;
  branch_moves: string[];
}
