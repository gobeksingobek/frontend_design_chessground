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

export interface AnalysisRunHistoryEntry {
  job_id: string;
  run_type: AnalysisRunType;
  state: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface AnalysisRunHistoryResponse {
  runs: AnalysisRunHistoryEntry[];
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

export interface TrainerSessionItem {
  branch_id: string;
  fen: string;
  prompt: string;
  expected_move_uci: string;
  difficulty: "easy" | "medium" | "hard";
}

export interface TrainerQueueSnapshot {
  remaining: number;
  learned: number;
  needs_review: number;
}

export interface TrainerSessionResponse {
  session_id: string;
  item: TrainerSessionItem;
  queue_snapshot: TrainerQueueSnapshot;
}

export interface TrainerSessionAnswerRequest {
  move_uci: string;
  elapsed_ms: number;
}

export interface TrainerSessionRemediation {
  best_move_uci: string;
  principal_variation: string[];
  explanation_markdown: string;
  retry_required: boolean;
}

export interface TrainerSessionAnswerResponse {
  outcome: "correct" | "incorrect";
  grade: "again" | "hard" | "good" | "easy";
  streak_delta: number;
  item_state: "learned" | "needs_review";
  next_item?: TrainerSessionItem | null;
  remediation?: TrainerSessionRemediation | null;
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

export interface ReviewPropositionDetail extends ReviewProposition {
  proposition_key: string;
  dismissed_count: number | null;
  detail: Record<string, unknown> | null;
  created_at: string | null;
  decided_at: string | null;
}

export interface BranchQueueEntry {
  proposition_id: number;
  queue_status: string;
  queued_at: string | null;
  proposition_status: string;
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
  proposition: ReviewPropositionDetail | null;
  status_change: { before: string | null; after: string | null } | null;
  queue_change: { before: BranchQueueEntry | null; after: BranchQueueEntry | null } | null;
  priority_change: { line_id: string | null; before: number | null; after: number | null } | null;
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
  repertoire_dir: string | null;
  games_dir: string | null;
  database_path: string | null;
  stockfish_path: string | null;
  piece_dir: string | null;
  engine_depth: number | null;
  max_plies: number | null;
  player_name: string | null;
  player_names: string[];
  rating_band_size: number | null;
  matching_mode: string | null;
  enable_engine_cache: boolean | null;
  incremental_analysis: boolean | null;
  review_top_n: number | null;
  tabiya_top_n: number | null;
  engine_workers: number | null;
  engine_worker_cap: number | null;
  engine_threads: number | null;
  engine_hash_mb: number | null;
  engine_mode: string | null;
  engine_max_time_ms: number | null;
  engine_profile: string | null;
  engine_cache_prune_non_active: boolean | null;
  missing_coverage_proposal_threshold: number | null;
}

export interface RuntimeSettingsUpdateRequest {
  chesscom_usernames: string[];
  lichess_usernames: string[];
  variants: string[];
  days_back: number;
  repertoire_dir?: string;
  games_dir?: string;
  database_path?: string;
  stockfish_path?: string;
  piece_dir?: string;
  engine_depth?: number;
  max_plies?: number;
  player_name?: string;
  player_names?: string[];
  rating_band_size?: number;
  matching_mode?: string;
  enable_engine_cache?: boolean;
  incremental_analysis?: boolean;
  review_top_n?: number;
  tabiya_top_n?: number;
  engine_workers?: number;
  engine_worker_cap?: number;
  engine_threads?: number;
  engine_hash_mb?: number;
  engine_mode?: string;
  engine_max_time_ms?: number;
  engine_profile?: string;
  engine_cache_prune_non_active?: boolean;
  missing_coverage_proposal_threshold?: number;
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
