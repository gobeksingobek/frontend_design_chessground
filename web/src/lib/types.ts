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
  prev_game_id: number | null;
  next_game_id: number | null;
}

export interface OverviewSummary {
  lines: number;
  manual_priority: number;
  auto_priority: number;
  games: number;
  matched: number;
  fully_compliant: number;
}

export type StatsRow = Record<string, string | number | boolean | null>;

export interface TreeNodeSummary {
  id: string;
  parent_id: string | null;
  fen: string;
  san_move: string | null;
  uci_move: string | null;
  depth: number;
  branch_depth: number;
  coverage: number;
  child_count: number;
}

export interface TreeExplorerResponse {
  nodes: TreeNodeSummary[];
}

export interface TreeBrowseMove {
  uci_move: string;
  san_move: string | null;
  next_pos_id: number | null;
  weight: number;
  is_priority_edge: number;
  is_user_mainline: number;
  is_sideline_pending: number;
}

export interface TreeGameMove {
  uci_move: string;
  san_move: string | null;
  next_pos_id: number | null;
  games: number;
  wins: number;
  draws: number;
  losses: number;
  avg_opp_elo: number | null;
  score_pct: number;
}

export interface TreeBrowseResponse {
  pos_id: number;
  my_side_only: boolean;
  repertoire_children: TreeBrowseMove[];
  game_children: TreeGameMove[];
}

export interface TreeCoverageResponse {
  pos_id: number;
  total_repertoire_moves: number;
  covered_by_games: number;
  coverage_pct: number;
}

export interface TreeBranchMetricsResponse {
  pos_id: number;
  top_repertoire_branches: TreeBrowseMove[];
  top_game_branches: TreeGameMove[];
}

export interface TrainerQueueItem {
  line_id: string;
  side_to_play: string;
  learned: number;
  needs_review: number;
  correct_streak: number;
  priority_override: number;
  auto_priority_score: number;
  focus_max_ply: number | null;
  is_priority: number;
}

export interface TrainerQueueResponse {
  mode: "learn" | "review";
  items: TrainerQueueItem[];
}

export interface TrainerOutcomeRequest {
  line_id: string;
  is_correct: boolean;
  mode: "learn" | "review";
}

export interface TrainerOutcomeResponse {
  line_id: string;
  learned: number;
  needs_review: number;
  correct_streak: number;
  times_correct: number;
  times_incorrect: number;
}



export interface TrainerSessionCreateRequest {
  mode: "learn" | "review";
  line_id?: string;
}

export interface TrainerSessionNextStep {
  phase: "prompt" | "user_attempt" | "reveal_explanation" | "grading" | "next_item_transition" | "completed";
  expected_move_uci: string | null;
  explanation: string | null;
}

export interface TrainerSessionResponse {
  session_id: string;
  line_id: string;
  mode: "learn" | "review";
  player_move_index: number;
  expected_move_uci: string | null;
  completed: boolean;
  next_step: TrainerSessionNextStep;
}

export interface TrainerSessionAnswerRequest {
  answer_uci: string;
}

export interface TrainerSessionAnswerResponse {
  session_id: string;
  line_id: string;
  mode: "learn" | "review";
  answer_uci: string;
  expected_move_uci: string | null;
  is_correct: boolean;
  feedback: string;
  learned: number;
  needs_review: number;
  correct_streak: number;
  times_correct: number;
  times_incorrect: number;
  completed: boolean;
  next_step: TrainerSessionNextStep;
}

export interface TrainerPriorityOverrideRequest {
  line_id: string;
  value: -1 | 0 | 1;
}

export interface TrainerAnswerRequest {
  item_id: string;
  answer_uci: string;
}

export interface TrainerAnswerResult {
  item_id: string;
  is_correct: boolean;
  correct_uci: string | null;
  score_delta: number;
  message: string;
}

export interface ReviewProposition {
  id: number;
  proposition_type: string;
  status: string;
  evidence_count: number;
  threshold_count: number;
  pos_id: number;
  uci_move: string;
  line_id_hint: string | null;
  updated_at: string;
}

export interface ReviewActionRequest {
  proposition_id: number;
  action: "done" | "defer" | "priority";
}

export interface ReviewActionResponse {
  success: boolean;
  message: string;
}

export type AnalysisRunType = "full-analysis" | "engine-only-analysis" | "fetch-games" | "smoke-test";
export type AnalysisJobState = "idle" | "running" | "completed" | "failed";

export interface AnalysisRunResponse {
  accepted: boolean;
  detail: string;
  job_id: string;
  run_type: AnalysisRunType;
}

export interface AnalysisStatusResponse {
  state: AnalysisJobState;
  active_job_id: string | null;
  active_run_type: AnalysisRunType | null;
  last_completed_job_id: string | null;
  last_run_type: AnalysisRunType | null;
  last_error: string | null;
  updated_at: string;
}

export interface AnalysisProgressResponse {
  job_id: string | null;
  run_type: AnalysisRunType | null;
  progress: Record<string, unknown> | null;
  updated_at: string;
}

export interface RuntimeSettings {
  chesscom_usernames: string[];
  lichess_usernames: string[];
  variants: string[];
  days_back: number;
  games_dir: string | null;
  database_path: string | null;
}

export interface RuntimeSettingsUpdateRequest {
  chesscom_usernames: string[];
  lichess_usernames: string[];
  variants: string[];
  days_back: number;
}


export interface RepertoireImportResponse {
  job_id: string;
  status: "completed";
  upload_hash: string;
  inserted_lines: number;
  duplicate_lines: number;
  total_lines: number;
  detail: string;
}

export interface RepertoireImportJobResponse {
  id: string;
  status: "completed";
  progress: Record<string, unknown>;
}
