export type SidelineStatus = "queued" | "processing" | "retry" | "failed" | "completed";

export type EvalConfidenceTag = "high" | "medium" | "low" | "unavailable";

export interface SidelineEvalMetadata {
  cpl_estimate: number | null;
  eval_depth: number | null;
  eval_time_ms: number | null;
  confidence_tag: EvalConfidenceTag;
  candidate_move_uci: string | null;
  budget_depth: number;
  budget_time_ms: number;
  engine: "stockfish_wasm";
}

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
  eval_metadata?: SidelineEvalMetadata;
}

export interface GameOverview {
  id: number;
  date: string | null;
  white: string | null;
  black: string | null;
  result: string | null;
  time_control: string | null;
  white_elo: number | null;
  black_elo: number | null;
  line_id: string | null;
  compliance: string | null;
  max_matched_ply: number | null;
  matching_mode: string | null;
  who_left_first: string | null;
  in_main: number | null;
  in_other: number | null;
  out_rep: number | null;
}

export interface GameMove {
  ply: number;
  pos_id: number;
  fen: string | null;
  san_move: string | null;
  uci_move: string | null;
  repertoire_class: string | null;
  is_self: number;
  clock_seconds: number | null;
  time_spent_seconds: number | null;
  time_spent_fraction: number | null;
  pre_eval_cp: number | null;
  post_eval_cp: number | null;
  best_uci: string | null;
  your_cpl: number | null;
  rep_cpl: number | null;
  quality_label: string | null;
}

export interface GameDetail {
  header: Record<string, unknown>;
  moves: GameMove[];
}
