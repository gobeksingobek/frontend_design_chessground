from __future__ import annotations

import uuid
import asyncio
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Literal

import asyncpg
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AliasChoices, BaseModel, Field

from backend import db
from backend import jobs
from backend.queue import enqueue_job, ensure_all_consumer_groups, redis_client
from backend.read_api import (
    ALLOWED_RATING_BAND_SIZES,
    build_position_intelligence_payload,
    build_tree_contract_payload,
    fetch_game_detail,
    fetch_games,
    fetch_insights,
    fetch_line_stats_detail,
    fetch_line_stats_history,
    fetch_lines_stats,
    fetch_overview_summary,
    fetch_rating_band_stats_payload,
    fetch_review_items,
    fetch_time_usage_stats,
    normalize_rating_band_size,
)
from backend.settings import DEFAULT_RUNTIME_SETTINGS, SETTINGS, merge_runtime_settings_payload


logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class ValidationErrorResponse(BaseModel):
    detail: list[dict[str, Any]]


class EvalMetadata(BaseModel):
    cpl_estimate: float | None = None
    eval_depth: int | None = Field(default=None, ge=0)
    eval_time_ms: int | None = Field(default=None, ge=0)
    confidence_tag: Literal["high", "medium", "low", "unavailable"]
    candidate_move_uci: str | None = None
    budget_depth: int = Field(ge=1)
    budget_time_ms: int = Field(ge=1)
    engine: Literal["stockfish_wasm"]


class SidelineCreateRequest(BaseModel):
    game_id: str = Field(min_length=1, examples=["game-12345"])
    move_ply: int = Field(ge=1, examples=[12])
    fen: str = Field(min_length=1, examples=["rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"])
    branch_moves: list[str] = Field(min_length=1, examples=[["d7d5", "c2c4"]])
    eval_metadata: EvalMetadata | None = None


class SidelineResponse(BaseModel):
    id: str
    job_id: str
    job_type: Literal["sideline-analysis"] = "sideline-analysis"
    status_url: str
    game_id: str
    move_ply: int
    requested_by: str
    status: str
    idempotency_key: str
    attempts: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class GameOverviewResponse(BaseModel):
    id: int
    date: str | None
    white: str | None
    black: str | None
    result: str | None
    time_control: str | None
    white_elo: int | None
    black_elo: int | None
    line_id: str | None
    compliance: str | None
    max_matched_ply: int | None
    matching_mode: str | None
    who_left_first: str | None
    in_main: int | None
    in_other: int | None
    out_rep: int | None


class GameMoveResponse(BaseModel):
    ply: int
    pos_id: int
    fen: str | None
    san_move: str | None
    uci_move: str | None
    repertoire_class: str | None
    is_self: int
    clock_seconds: float | None
    time_spent_seconds: float | None
    time_spent_fraction: float | None
    pre_eval_cp: int | None
    post_eval_cp: int | None
    best_uci: str | None
    your_cpl: int | None
    rep_cpl: int | None
    quality_label: str | None


class GameDetailResponse(BaseModel):
    class NavigationResponse(BaseModel):
        current_game_id: int | None = None
        prev_game_id: int | None = None
        next_game_id: int | None = None
        bookmarked_ply_ids: list[int] = Field(default_factory=list)
        can_jump_start: bool = False
        can_jump_end: bool = False

    header: dict[str, Any]
    moves: list[GameMoveResponse]
    prev_game_id: int | None = None
    next_game_id: int | None = None
    prev_game_label: str | None = None
    next_game_label: str | None = None
    navigation: NavigationResponse


class TimeUsagePivot(str):
    SELF_VS_OPP = "self_vs_opp"
    IN_BOOK_VS_OUT_OF_BOOK = "in_book_vs_out_of_book"


class TimeUsageStatsResponse(BaseModel):
    pivot: Literal["self_vs_opp", "in_book_vs_out_of_book"]
    buckets: list[dict[str, Any]]
    totals: dict[str, Any]


class RatingBandStatsResponse(BaseModel):
    band_size: int
    allowed_band_sizes: list[int]
    percentiles: dict[str, float | None]
    totals: dict[str, Any]
    buckets: list[dict[str, Any]]


class AnalysisRunResponse(BaseModel):
    accepted: bool
    detail: str
    job_id: str
    run_type: str
    job_type: str
    status: str
    status_url: str


class JobResponse(BaseModel):
    job_id: str
    workspace_id: str
    parent_job_id: str | None = None
    job_type: str
    status: str
    priority: int
    idempotency_key: str
    request: dict[str, Any]
    progress: dict[str, Any]
    result: Any = None
    error_code: str | None = None
    error_detail: str | None = None
    attempts: int
    max_attempts: int
    cancellation_requested: bool
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobStepResponse(BaseModel):
    step_id: str
    job_id: str
    workspace_id: str
    workload_class: str
    step_type: str
    status: str
    payload: dict[str, Any]
    result: Any = None
    deduplication_key: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    error_code: str | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class AnalysisFetchGamesResult(BaseModel):
    source: str
    username: str
    fetched_files: int
    skipped_files: int
    games_seen: int
    games_written: int
    games_skipped_in_db: int
    message: str


class AnalysisStatusResponse(BaseModel):
    state: Literal["idle", "running", "completed", "failed"]
    active_job_id: str | None
    active_run_type: str | None
    last_completed_job_id: str | None
    last_run_type: str | None
    last_error: str | None
    updated_at: str


class AnalysisProgressResponse(BaseModel):
    job_id: str | None
    run_type: str | None
    progress: dict[str, Any] | None
    updated_at: str


class AnalysisRunHistoryEntry(BaseModel):
    run_id: str = Field(validation_alias=AliasChoices("run_id", "job_id"))
    run_type: str
    status: Literal["running", "completed", "failed"] = Field(validation_alias=AliasChoices("status", "state"))
    started_at: str
    finished_at: str | None = None
    error_reason: str | None = Field(default=None, validation_alias=AliasChoices("error_reason", "error"))

    @property
    def job_id(self) -> str:  # backwards compatibility
        return self.run_id

    @property
    def state(self) -> str:  # backwards compatibility
        return self.status

    @property
    def error(self) -> str | None:  # backwards compatibility
        return self.error_reason


class AnalysisRunHistoryResponse(BaseModel):
    runs: list[AnalysisRunHistoryEntry]


class TreeBrowseMoveResponse(BaseModel):
    uci_move: str
    san_move: str | None = None
    next_pos_id: int | None = None
    weight: int = 0
    is_priority_edge: int = 0
    is_user_mainline: int = 0
    is_sideline_pending: int = 0


class TreeBrowseResponse(BaseModel):
    pos_id: int
    my_side_only: bool
    repertoire_children: list[TreeBrowseMoveResponse]
    game_children: list[dict[str, Any]]


class TreeCoverageResponse(BaseModel):
    pos_id: int
    my_side_only: bool
    repertoire_children: list[TreeBrowseMoveResponse]
    game_children: list[dict[str, Any]]
    total_repertoire_moves: int
    covered_by_games: int
    coverage_pct: float


class TreeBranchMetricsResponse(BaseModel):
    pos_id: int
    my_side_only: bool
    repertoire_children: list[TreeBrowseMoveResponse]
    game_children: list[dict[str, Any]]
    top_repertoire_branches: list[dict[str, Any]]
    top_game_branches: list[dict[str, Any]]


class PositionIntelligenceResponse(BaseModel):
    pos_id: int
    my_side_only: bool
    position: dict[str, Any]
    repertoire_continuations: list[TreeBrowseMoveResponse]
    game_continuations: list[dict[str, Any]]
    coverage: dict[str, Any]
    outcome_summary: dict[str, Any]
    evaluation_summary: dict[str, Any]
    recent_games: list[dict[str, Any]]
    evidence: dict[str, Any]


class TrainerQueueEntry(BaseModel):
    line_id: str
    side_to_play: str
    learned: int
    needs_review: int
    correct_streak: int
    priority_override: int
    auto_priority_score: int
    focus_max_ply: int | None = None
    is_priority: int


class TrainerQueueResponse(BaseModel):
    mode: Literal["learn", "review"]
    items: list[TrainerQueueEntry]


class TrainerOutcomeRequest(BaseModel):
    line_id: str = Field(min_length=1)
    is_correct: bool | None = None
    outcome: Literal["correct", "incorrect"] | None = None
    grade: Literal["again", "hard", "good", "easy"] | None = None
    mode: Literal["learn", "review"] = "review"


class TrainerOutcomeResponse(BaseModel):
    line_id: str
    learned: int
    needs_review: int
    correct_streak: int
    times_correct: int
    times_incorrect: int


class TrainerPriorityOverrideRequest(BaseModel):
    line_id: str = Field(min_length=1)
    value: Literal[-1, 0, 1]


class MainlineOverrideRequest(BaseModel):
    uci_move: str = Field(min_length=4, max_length=5)
    next_pos_id: int = Field(ge=1)




class TrainerSessionCreateRequest(BaseModel):
    mode: Literal["learn", "review"] = "review"
    line_id: str | None = Field(default=None, min_length=1)


class TrainerSessionItem(BaseModel):
    branch_id: str
    fen: str
    prompt: str
    expected_move_uci: str
    difficulty: Literal["easy", "medium", "hard"]


class TrainerQueueSnapshot(BaseModel):
    remaining: int = Field(ge=0)
    learned: int = Field(ge=0)
    needs_review: int = Field(ge=0)


class TrainerSessionResponse(BaseModel):
    session_id: str
    item: TrainerSessionItem
    queue_snapshot: TrainerQueueSnapshot


class TrainerSessionRemediation(BaseModel):
    best_move_uci: str
    principal_variation: list[str]
    explanation_markdown: str
    retry_required: bool


class TrainerSessionAnswerRequest(BaseModel):
    move_uci: str = Field(min_length=4, max_length=5)
    elapsed_ms: int = Field(ge=0)


class TrainerSessionAnswerResponse(BaseModel):
    outcome: Literal["correct", "incorrect"]
    grade: Literal["again", "hard", "good", "easy"]
    streak_delta: int
    item_state: Literal["learned", "needs_review"]
    next_item: TrainerSessionItem | None = None
    remediation: TrainerSessionRemediation | None = None

class ReviewPropositionResponse(BaseModel):
    id: int
    proposition_type: str
    status: str
    evidence_count: int
    threshold_count: int
    pos_id: int
    uci_move: str
    line_id_hint: str | None = None
    updated_at: datetime


class ReviewPropositionDetailResponse(ReviewPropositionResponse):
    proposition_key: str
    dismissed_count: int | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None


class BranchQueueEntryResponse(BaseModel):
    proposition_id: int
    queue_status: str
    queued_at: datetime | None = None
    proposition_status: str
    evidence_count: int
    threshold_count: int
    pos_id: int
    uci_move: str
    line_id_hint: str | None = None
    updated_at: datetime


class ReviewQueueDelta(BaseModel):
    proposition_id: int
    before_queue_status: str | None = None
    after_queue_status: str | None = None
    added_to_queue: bool
    removed_from_queue: bool


class ReviewActionDelta(BaseModel):
    before: Any = None
    after: Any = None


class ReviewPriorityDelta(BaseModel):
    line_id: str | None = None
    before: int | None = None
    after: int | None = None


class ReviewActionRequest(BaseModel):
    proposition_id: int = Field(ge=1)
    action: Literal["done", "defer", "priority"]


class ReviewActionResponse(BaseModel):
    success: bool
    message: str
    proposition: ReviewPropositionDetailResponse | None = None
    status_change: ReviewActionDelta | None = None
    queue_change: ReviewActionDelta | None = None
    queue_delta: ReviewQueueDelta | None = None
    priority_change: ReviewPriorityDelta | None = None


class AuthValidateResponse(BaseModel):
    ok: bool
    detail: str


class RuntimeSettingsResponse(BaseModel):
    chesscom_usernames: list[str]
    lichess_usernames: list[str]
    variants: list[str]
    days_back: int = Field(ge=1)
    engine_depth: int | None = None
    max_plies: int | None = None
    player_name: str | None = None
    player_names: list[str] = Field(default_factory=list)
    rating_band_size: int | None = None
    matching_mode: str | None = None
    enable_engine_cache: bool | None = None
    incremental_analysis: bool | None = None
    review_top_n: int | None = None
    tabiya_top_n: int | None = None
    missing_coverage_proposal_threshold: int | None = None


class RuntimeSettingsUpdateRequest(BaseModel):
    chesscom_usernames: list[str] = Field(default_factory=list)
    lichess_usernames: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    days_back: int = Field(ge=1, le=3650)
    engine_depth: int | None = Field(default=None, ge=1)
    max_plies: int | None = Field(default=None, ge=1)
    player_name: str | None = None
    player_names: list[str] | None = None
    rating_band_size: int | None = Field(default=None, ge=1)
    matching_mode: str | None = None
    enable_engine_cache: bool | None = None
    incremental_analysis: bool | None = None
    review_top_n: int | None = Field(default=None, ge=1)
    tabiya_top_n: int | None = Field(default=None, ge=1)
    missing_coverage_proposal_threshold: int | None = Field(default=None, ge=1)






class RepertoireImportResponse(BaseModel):
    job_id: str
    job_type: Literal["repertoire-import"] = "repertoire-import"
    status_url: str
    status: Literal["queued", "running", "retry", "completed", "failed", "cancelled"]
    upload_hash: str
    inserted_lines: int = 0
    duplicate_lines: int = 0
    total_lines: int = 0
    detail: str


class RepertoireImportJobResponse(BaseModel):
    id: str
    status: str
    progress: dict[str, Any]

def _require_postgres_request(request: Request | None) -> Request:
    if request is None:
        raise api_error(500, "INTERNAL_ERROR", "Request context is required for PostgreSQL backend access.")
    return request


async def _fetch_tree_repertoire_children_backend(
    pos_id: int,
    my_side_only: bool,
    request: Request | None,
) -> list[dict[str, Any]]:
    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH repertoire_rows AS (
                SELECT lp.uci_move,
                       MIN(lp.san_move) AS san_move,
                       lp.next_pos_id,
                       COALESCE(MAX(re.weight), COUNT(*))::int AS weight,
                       MAX(CASE WHEN rl.is_priority = 1 THEN 1 ELSE 0 END)::int AS is_priority_edge,
                       MAX(CASE WHEN override.uci_move = lp.uci_move
                                     AND override.next_pos_id = lp.next_pos_id THEN 1 ELSE 0 END)::int AS is_user_mainline,
                       SUM(
                           CASE
                               WHEN (
                                   (rl.side_to_play = 'white' AND MOD(lp.ply, 2) = 1)
                                   OR
                                   (rl.side_to_play = 'black' AND MOD(lp.ply, 2) = 0)
                               )
                               THEN 1
                               ELSE 0
                           END
                       )::int AS self_count,
                       0::int AS is_sideline_pending
                FROM line_positions lp
                JOIN repertoire_lines rl
                  ON rl.workspace_id = lp.workspace_id AND rl.line_id = lp.line_id
                LEFT JOIN repertoire_edges re
                  ON re.workspace_id = lp.workspace_id AND re.pos_id = lp.pos_id
                 AND re.uci_move = lp.uci_move AND re.next_pos_id = lp.next_pos_id
                LEFT JOIN user_mainline_overrides override
                  ON override.workspace_id = lp.workspace_id AND override.pos_id = lp.pos_id
                WHERE lp.workspace_id = $3::uuid AND lp.pos_id = $1
                GROUP BY lp.uci_move, lp.next_pos_id
            ),
            pending_sidelines AS (
                SELECT sr.payload -> 'branch_moves' ->> 0 AS uci_move,
                       sr.payload -> 'branch_moves' ->> 0 AS san_move,
                       NULL::bigint AS next_pos_id,
                       0::int AS weight,
                       0::int AS is_priority_edge,
                       0::int AS is_user_mainline,
                       CASE WHEN $2 = 1 THEN 1 ELSE 0 END::int AS self_count,
                       1::int AS is_sideline_pending
                FROM sideline_requests sr
                JOIN analysis_jobs job ON job.id = sr.job_id
                JOIN positions position ON position.fen_norm = sr.payload ->> 'fen'
                WHERE sr.workspace_id = $3::uuid AND position.id = $1
                  AND job.status IN ('queued', 'running', 'retry')
                  AND NOT EXISTS (
                      SELECT 1 FROM repertoire_rows rr
                      WHERE rr.uci_move = sr.payload -> 'branch_moves' ->> 0
                  )
            )
            SELECT uci_move, san_move, next_pos_id, weight, is_priority_edge, is_user_mainline, self_count, is_sideline_pending
            FROM repertoire_rows
            WHERE ($2 = 0 OR self_count > 0)
            UNION ALL
            SELECT uci_move, san_move, next_pos_id, weight, is_priority_edge, is_user_mainline, self_count, is_sideline_pending
            FROM pending_sidelines
            ORDER BY is_sideline_pending DESC, weight DESC, uci_move
            """,
            int(pos_id),
            1 if my_side_only else 0,
            SETTINGS.workspace_id,
        )
    return [dict(row) for row in rows]


async def _fetch_tree_game_children_backend(
    pos_id: int,
    my_side_only: bool,
    request: Request | None,
) -> list[dict[str, Any]]:
    req = _require_postgres_request(request)
    where_clause = "gp.pos_id = $1 AND gp.is_self = 1" if my_side_only else "gp.pos_id = $1"
    async with req.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT gp.uci_move,
                   MIN(gp.san_move) AS san_move,
                   MIN(gp_next.pos_id) AS next_pos_id,
                   COUNT(*)::int AS games,
                   SUM(
                       CASE
                           WHEN (
                               (g.result = '1-0' AND g.player_color = 'white')
                               OR
                               (g.result = '0-1' AND g.player_color = 'black')
                           ) THEN 1 ELSE 0
                       END
                   )::int AS wins,
                   SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END)::int AS draws,
                   SUM(
                       CASE
                           WHEN (
                               (g.result = '0-1' AND g.player_color = 'white')
                               OR
                               (g.result = '1-0' AND g.player_color = 'black')
                           ) THEN 1 ELSE 0
                       END
                   )::int AS losses,
                   AVG(
                       CASE
                           WHEN g.player_color = 'white' THEN g.black_elo
                           ELSE g.white_elo
                       END
                   ) AS avg_opp_elo
            FROM game_positions gp
            JOIN games g
              ON g.workspace_id = gp.workspace_id AND g.id = gp.game_id
            LEFT JOIN game_positions gp_next
              ON gp_next.workspace_id = gp.workspace_id AND gp_next.game_id = gp.game_id
             AND gp_next.ply = gp.ply + 1
            WHERE gp.workspace_id = $2::uuid AND {where_clause}
            GROUP BY gp.uci_move
            ORDER BY games DESC, gp.uci_move
            """,
            int(pos_id),
        )

    out: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        total = int(entry.get("games") or 0)
        wins = int(entry.get("wins") or 0)
        draws = int(entry.get("draws") or 0)
        entry["score_pct"] = ((wins + 0.5 * draws) / total * 100.0) if total > 0 else 0.0
        out.append(entry)
    return out


async def _fetch_position_intelligence_summary_backend(
    pos_id: int,
    request: Request | None,
    limit: int = 8,
) -> dict[str, Any]:
    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        position = await conn.fetchrow(
            """
            SELECT id AS pos_id,
                   fen_norm AS fen,
                   CASE
                       WHEN array_length(string_to_array(fen_norm, ' '), 1) >= 2
                       THEN split_part(fen_norm, ' ', 2)
                       ELSE NULL
                   END AS side_to_move
            FROM positions
            WHERE id = $1
            """,
            int(pos_id),
        )
        totals = await conn.fetchrow(
            """
            SELECT COUNT(DISTINCT gp.game_id)::int AS games,
                   SUM(CASE WHEN g.result = '1-0' AND g.player_color = 'white' THEN 1
                            WHEN g.result = '0-1' AND g.player_color = 'black' THEN 1
                            ELSE 0 END)::int AS wins,
                   SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END)::int AS draws,
                   SUM(CASE WHEN g.result = '0-1' AND g.player_color = 'white' THEN 1
                            WHEN g.result = '1-0' AND g.player_color = 'black' THEN 1
                            ELSE 0 END)::int AS losses,
                   SUM(CASE WHEN m.deviation_ply_opp = gp.ply THEN 1 ELSE 0 END)::int AS opponent_deviation_count
            FROM game_positions gp
            JOIN games g ON g.workspace_id = gp.workspace_id AND g.id = gp.game_id
            LEFT JOIN workspace_state ws ON ws.workspace_id = gp.workspace_id
            LEFT JOIN matches m ON m.workspace_id = gp.workspace_id AND m.game_id = gp.game_id
                               AND m.analysis_run_id = ws.active_analysis_run_id
            WHERE gp.pos_id = $1 AND gp.workspace_id = $2::uuid
            """,
            int(pos_id),
            SETTINGS.workspace_id,
        )
        evals = await conn.fetchrow(
            """
            SELECT AVG(ap.post_eval_cp) AS avg_exit_eval_cp,
                   AVG(ap.your_cpl) AS avg_your_cpl,
                   AVG(ap.rep_cpl) AS avg_rep_cpl
            FROM analysis_ply ap
            JOIN workspace_state ws ON ws.workspace_id = ap.workspace_id
                                   AND ws.active_analysis_run_id = ap.analysis_run_id
            WHERE ap.pos_id = $1 AND ap.workspace_id = $2::uuid
            """,
            int(pos_id),
            SETTINGS.workspace_id,
        )
        has_engine_cache = bool(await conn.fetchval("SELECT to_regclass('public.engine_cache') IS NOT NULL"))
        latest_engine = None
        if has_engine_cache:
            latest_engine = await conn.fetchrow(
                """
                SELECT best_uci, eval_cp, depth, engine_id, analyzed_at
                FROM engine_cache
                WHERE pos_id = $1
                ORDER BY depth DESC, analyzed_at DESC
                LIMIT 1
                """,
                int(pos_id),
            )
        recent_games = await conn.fetch(
            """
            SELECT g.id AS game_id,
                   g.date,
                   g.white,
                   g.black,
                   g.result,
                   g.player_color,
                   gp.ply,
                   gp.san_move,
                   gp.uci_move,
                   gp.repertoire_class,
                   ap.post_eval_cp,
                   ap.your_cpl
            FROM game_positions gp
            JOIN games g ON g.workspace_id = gp.workspace_id AND g.id = gp.game_id
            LEFT JOIN workspace_state ws ON ws.workspace_id = gp.workspace_id
            LEFT JOIN analysis_ply ap ON ap.workspace_id = gp.workspace_id
                                     AND ap.game_id = gp.game_id AND ap.ply = gp.ply
                                     AND ap.analysis_run_id = ws.active_analysis_run_id
            WHERE gp.pos_id = $1 AND gp.workspace_id = $3::uuid
            ORDER BY g.date DESC, g.id DESC, gp.ply ASC
            LIMIT $2
            """,
            int(pos_id),
            int(limit),
            SETTINGS.workspace_id,
        )

    return {
        "position": dict(position) if position else {"pos_id": int(pos_id), "fen": None, "side_to_move": None},
        "totals": dict(totals) if totals else {},
        "evals": dict(evals) if evals else {},
        "latest_engine": dict(latest_engine) if latest_engine else None,
        "recent_games": [dict(row) for row in recent_games],
    }


async def _fetch_review_propositions_backend(
    status_filter: str,
    request: Request | None,
) -> list[dict[str, Any]]:
    status_key = (status_filter or "pending").strip().lower()
    where = ["workspace_id = $1::uuid", "proposition_type = 'MISSING_COVERAGE_BRANCH'"]
    if status_key == "pending":
        where.append("status = 'PENDING'")
        where.append("evidence_count > threshold_count")
    elif status_key == "approved":
        where.append("status = 'APPROVED'")
    elif status_key == "disapproved":
        where.append("status = 'DISAPPROVED'")
    elif status_key != "all":
        where.append("status = 'PENDING'")
        where.append("evidence_count > threshold_count")

    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id,
                   proposition_type,
                   status,
                   evidence_count,
                   threshold_count,
                   pos_id,
                   uci_move,
                   line_id_hint,
                   updated_at
            FROM review_propositions
            WHERE {' AND '.join(where)}
            ORDER BY evidence_count DESC, updated_at DESC, id DESC
            """,
            SETTINGS.workspace_id,
        )
    return [dict(row) for row in rows]


async def _fetch_review_proposition_detail_backend(
    proposition_id: int,
    request: Request | None,
) -> dict[str, Any] | None:
    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id,
                   proposition_type,
                   proposition_key,
                   status,
                   evidence_count,
                   threshold_count,
                   dismissed_count,
                   pos_id,
                   uci_move,
                   line_id_hint,
                   detail_json,
                   created_at,
                   updated_at,
                   decided_at
            FROM review_propositions
            WHERE id = $1 AND workspace_id = $2::uuid
            """,
            int(proposition_id),
            SETTINGS.workspace_id,
        )
    if not row:
        return None
    data = dict(row)
    payload = data.get("detail_json")
    data["detail"] = json.loads(payload) if isinstance(payload, str) else payload
    return data


async def _fetch_branch_queue_backend(request: Request | None) -> list[dict[str, Any]]:
    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT bq.proposition_id,
                   bq.queue_status,
                   bq.queued_at,
                   rp.status AS proposition_status,
                   rp.evidence_count,
                   rp.threshold_count,
                   rp.pos_id,
                   rp.uci_move,
                   rp.line_id_hint,
                   rp.updated_at
            FROM branch_queue bq
            JOIN review_propositions rp ON rp.id = bq.proposition_id
            WHERE bq.workspace_id = $1::uuid AND rp.workspace_id = $1::uuid
            ORDER BY bq.queued_at DESC, bq.proposition_id DESC
            """,
            SETTINGS.workspace_id,
        )
    return [dict(row) for row in rows]


async def _execute_review_action_backend(
    proposition_id: int,
    action: str,
    request: Request | None,
) -> dict[str, Any]:
    pid = int(proposition_id)
    action_key = (action or "").strip().lower()
    now = datetime.now(timezone.utc)

    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        async with conn.transaction():
            detail_row = await conn.fetchrow(
                """
                SELECT id, status, evidence_count, line_id_hint
                FROM review_propositions
                WHERE id = $1 AND workspace_id = $2::uuid
                """,
                pid,
                SETTINGS.workspace_id,
            )
            if not detail_row:
                return {"success": False, "message": "Proposition not found."}

            previous_status = str(detail_row["status"])
            line_id_hint = detail_row["line_id_hint"]

            queue_before_row = await conn.fetchrow(
                """
                SELECT bq.proposition_id,
                       bq.queue_status,
                       bq.queued_at,
                       rp.status AS proposition_status,
                       rp.evidence_count,
                       rp.threshold_count,
                       rp.pos_id,
                       rp.uci_move,
                       rp.line_id_hint,
                       rp.updated_at
                FROM branch_queue bq
                JOIN review_propositions rp ON rp.id = bq.proposition_id
                WHERE bq.proposition_id = $1 AND bq.workspace_id = $2::uuid
                """,
                pid,
                SETTINGS.workspace_id,
            )
            queue_before = dict(queue_before_row) if queue_before_row else None

            priority_before = None
            if line_id_hint:
                priority_before_row = await conn.fetchrow(
                    "SELECT priority_override FROM trainer_line_state WHERE line_id = $1 AND workspace_id = $2::uuid",
                    str(line_id_hint),
                    SETTINGS.workspace_id,
                )
                if priority_before_row:
                    priority_before = int(priority_before_row["priority_override"])

            if action_key == "done":
                tag = await conn.execute(
                    """
                    UPDATE review_propositions
                    SET status = 'APPROVED',
                        decided_at = $2,
                        updated_at = $2
                    WHERE id = $1 AND workspace_id = $3::uuid
                      AND proposition_type = 'MISSING_COVERAGE_BRANCH'
                    """,
                    pid,
                    now,
                    SETTINGS.workspace_id,
                )
                if tag.endswith('0'):
                    return {"success": False, "message": "Proposition not found."}
                await conn.execute(
                    """
                    INSERT INTO branch_queue (workspace_id, proposition_id, queue_status, queued_at)
                    VALUES ($3::uuid, $1, 'QUEUED', $2)
                    ON CONFLICT (proposition_id) DO UPDATE
                    SET queue_status = EXCLUDED.queue_status,
                        queued_at = EXCLUDED.queued_at
                    """,
                    pid,
                    now,
                    SETTINGS.workspace_id,
                )
                message = "Proposition approved and queued."
            elif action_key == "defer":
                await conn.execute(
                    """
                    UPDATE review_propositions
                    SET status = 'DISAPPROVED',
                        dismissed_count = $2,
                        decided_at = $3,
                        updated_at = $3
                    WHERE id = $1 AND workspace_id = $4::uuid
                      AND proposition_type = 'MISSING_COVERAGE_BRANCH'
                    """,
                    pid,
                    int(detail_row["evidence_count"] or 0),
                    now,
                    SETTINGS.workspace_id,
                )
                await conn.execute(
                    "DELETE FROM branch_queue WHERE proposition_id = $1 AND workspace_id = $2::uuid",
                    pid, SETTINGS.workspace_id,
                )
                message = "Proposition disapproved."
            elif action_key == "priority":
                if not line_id_hint:
                    return {"success": False, "message": "No line hint available to mark priority."}
                tag = await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET priority_override = 1
                    WHERE line_id = $1 AND workspace_id = $2::uuid
                    """,
                    str(line_id_hint),
                    SETTINGS.workspace_id,
                )
                if tag.endswith('0'):
                    return {"success": False, "message": "Line not found in trainer state."}
                await conn.execute(
                    """
                    UPDATE review_propositions
                    SET updated_at = $2
                    WHERE id = $1 AND workspace_id = $3::uuid
                    """,
                    pid,
                    now,
                    SETTINGS.workspace_id,
                )
                message = f"Priority override enabled for {line_id_hint}."
            else:
                return {"success": False, "message": "Unsupported review action."}

            updated_detail_row = await conn.fetchrow(
                """
                SELECT id,
                       proposition_type,
                       proposition_key,
                       status,
                       evidence_count,
                       threshold_count,
                       dismissed_count,
                       pos_id,
                       uci_move,
                       line_id_hint,
                       detail_json,
                       created_at,
                       updated_at,
                       decided_at
                FROM review_propositions
                WHERE id = $1 AND workspace_id = $2::uuid
                """,
                pid,
                SETTINGS.workspace_id,
            )
            updated_detail = dict(updated_detail_row) if updated_detail_row else None
            if updated_detail is not None:
                payload = updated_detail.get("detail_json")
                updated_detail["detail"] = json.loads(payload) if isinstance(payload, str) else payload

            queue_after_row = await conn.fetchrow(
                """
                SELECT bq.proposition_id,
                       bq.queue_status,
                       bq.queued_at,
                       rp.status AS proposition_status,
                       rp.evidence_count,
                       rp.threshold_count,
                       rp.pos_id,
                       rp.uci_move,
                       rp.line_id_hint,
                       rp.updated_at
                FROM branch_queue bq
                JOIN review_propositions rp ON rp.id = bq.proposition_id
                WHERE bq.proposition_id = $1 AND bq.workspace_id = $2::uuid
                """,
                pid,
                SETTINGS.workspace_id,
            )
            queue_after = dict(queue_after_row) if queue_after_row else None

            priority_after = None
            if line_id_hint:
                priority_after_row = await conn.fetchrow(
                    "SELECT priority_override FROM trainer_line_state WHERE line_id = $1 AND workspace_id = $2::uuid",
                    str(line_id_hint),
                    SETTINGS.workspace_id,
                )
                if priority_after_row:
                    priority_after = int(priority_after_row["priority_override"])

    return {
        "success": True,
        "message": message,
        "proposition": updated_detail,
        "status_change": {
            "before": previous_status,
            "after": (updated_detail or {}).get("status"),
        },
        "queue_change": {
            "before": queue_before,
            "after": queue_after,
        },
        "queue_delta": {
            "proposition_id": pid,
            "before_queue_status": (queue_before or {}).get("queue_status") if queue_before else None,
            "after_queue_status": (queue_after or {}).get("queue_status") if queue_after else None,
            "added_to_queue": queue_before is None and queue_after is not None,
            "removed_from_queue": queue_before is not None and queue_after is None,
        },
        "priority_change": {
            "line_id": line_id_hint,
            "before": priority_before,
            "after": priority_after,
        },
    }

async def _load_postgres_runtime_settings(pool: asyncpg.Pool) -> dict[str, Any]:
    persisted = await db.fetch_runtime_settings(pool)
    if persisted is not None:
        return {**DEFAULT_RUNTIME_SETTINGS, **persisted}
    seeded = dict(DEFAULT_RUNTIME_SETTINGS)
    await db.save_runtime_settings(pool, seeded)
    return seeded


async def _save_postgres_runtime_settings(pool: asyncpg.Pool, payload: dict[str, Any]) -> RuntimeSettingsResponse:
    current = await _load_postgres_runtime_settings(pool)
    saved, errors = merge_runtime_settings_payload(current, payload)
    if errors:
        raise HTTPException(
            status_code=422,
            detail=[{"field": err.field, "code": err.code, "message": err.message} for err in errors],
        )
    assert saved is not None
    await db.save_runtime_settings(pool, saved)
    return RuntimeSettingsResponse.model_validate(saved)


app = FastAPI(title="ChessGround API Service")
auth_scheme = HTTPBearer(auto_error=False)

if SETTINGS.api_cors_origins:
    allow_all_origins = len(SETTINGS.api_cors_origins) == 1 and SETTINGS.api_cors_origins[0] == "*"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(SETTINGS.api_cors_origins),
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def api_error(status_code: int, error_code: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error_code": error_code, "detail": detail})


async def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme)) -> str:
    expected = SETTINGS.api_auth_token
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != expected:
        raise api_error(status_code=401, error_code="UNAUTHORIZED", detail="Invalid or missing bearer token")
    return "api-user"


@app.on_event("startup")
async def on_startup() -> None:
    SETTINGS.validate_deployment_config("api")
    app.state.db_pool = await db.create_pool()
    await db.ensure_schema(app.state.db_pool)
    app.state.redis = redis_client()
    await ensure_all_consumer_groups(app.state.redis)
    missing = await db.ensure_analysis_schema_exists(app.state.db_pool)
    if missing:
        missing_csv = ", ".join(missing)
        raise RuntimeError(
            "PostgreSQL runtime schema is incomplete. "
            f"Missing table(s): {missing_csv}. "
            "Run `python -m backend.bootstrap_postgres_schema` before starting the API."
        )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await app.state.redis.aclose()
    await app.state.db_pool.close()


def to_response(record: asyncpg.Record) -> SidelineResponse:
    return SidelineResponse(
        id=str(record["id"]),
        job_id=str(record["job_id"]),
        status_url=f"/jobs/{record['job_id']}",
        game_id=record["game_id"],
        move_ply=record["move_ply"],
        requested_by=record["requested_by"],
        status=record["status"],
        idempotency_key=record["idempotency_key"],
        attempts=record["attempts"],
        result=record["result"],
        error=record["error"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


async def _enqueue_durable_job(
    request: Request,
    *,
    job_type: str,
    workload_class: Literal["orchestration", "engine", "ingest"],
    step_type: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with request.app.state.db_pool.acquire() as conn:
        durable_payload = dict(payload or {})
        if workload_class == "orchestration":
            artifact_ids = await conn.fetch(
                """
                SELECT id, source_type, content_hash FROM source_artifacts
                WHERE workspace_id = $1::uuid
                ORDER BY imported_at, id
                """,
                SETTINGS.workspace_id,
            )
            settings_row = await conn.fetchrow(
                "SELECT payload FROM runtime_settings WHERE workspace_id = $1::uuid",
                SETTINGS.workspace_id,
            )
            runtime_snapshot = settings_row["payload"] if settings_row else DEFAULT_RUNTIME_SETTINGS
            if isinstance(runtime_snapshot, str):
                runtime_snapshot = json.loads(runtime_snapshot)
            game_ids = await conn.fetch(
                "SELECT id FROM games WHERE workspace_id=$1::uuid ORDER BY id",
                SETTINGS.workspace_id,
            )
            durable_payload.update(
                source_artifact_ids=[str(row["id"]) for row in artifact_ids],
                source_artifacts=[
                    {
                        "id": str(row["id"]),
                        "source_type": str(row["source_type"]),
                        "content_hash": str(row["content_hash"]),
                    }
                    for row in artifact_ids
                ],
                settings_snapshot=dict(runtime_snapshot),
                game_ids_snapshot=[int(row["id"]) for row in game_ids],
                engine_profile={
                    "engine_id": SETTINGS.stockfish_engine_id,
                    "mode": "fixed",
                    "max_time_ms": 0,
                    "options_hash": "",
                },
            )
        job, step, created = await jobs.create_job(
            conn,
            job_type=job_type,
            workload_class=workload_class,
            step_type=step_type,
            request_payload=durable_payload,
            idempotency_key=idempotency_key,
        )
    if created:
        await enqueue_job(
            request.app.state.redis,
            workload_class,
            jobs.redis_message(step, job_type),
        )
    return job


def _accepted_job_response(job: dict[str, Any], detail: str = "Job accepted") -> AnalysisRunResponse:
    return AnalysisRunResponse(
        accepted=True,
        detail=detail,
        job_id=job["job_id"],
        run_type=job["job_type"],
        job_type=job["job_type"],
        status=job["status"],
        status_url=f"/jobs/{job['job_id']}",
    )


@app.get("/jobs", response_model=list[JobResponse])
async def list_durable_jobs(
    request: Request,
    status: str | None = None,
    type: str | None = None,
    limit: int = 20,
    _: str = Depends(require_auth),
) -> list[JobResponse]:
    async with request.app.state.db_pool.acquire() as conn:
        rows = await jobs.list_jobs(conn, status=status, job_type=type, limit=limit)
    return [JobResponse.model_validate(row) for row in rows]


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_durable_job(job_id: str, request: Request, _: str = Depends(require_auth)) -> JobResponse:
    async with request.app.state.db_pool.acquire() as conn:
        row = await jobs.get_job(conn, job_id)
    if row is None:
        raise api_error(404, "JOB_NOT_FOUND", "Job was not found.")
    return JobResponse.model_validate(row)


@app.get("/jobs/{job_id}/steps", response_model=list[JobStepResponse])
async def get_durable_job_steps(
    job_id: str, request: Request, _: str = Depends(require_auth)
) -> list[JobStepResponse]:
    async with request.app.state.db_pool.acquire() as conn:
        if await jobs.get_job(conn, job_id) is None:
            raise api_error(404, "JOB_NOT_FOUND", "Job was not found.")
        rows = await jobs.list_steps(conn, job_id)
    return [JobStepResponse.model_validate(row) for row in rows]


@app.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_durable_job(job_id: str, request: Request, _: str = Depends(require_auth)) -> JobResponse:
    async with request.app.state.db_pool.acquire() as conn:
        row = await jobs.cancel_job(conn, job_id)
    if row is None:
        raise api_error(404, "JOB_NOT_FOUND", "Job was not found.")
    return JobResponse.model_validate(row)


@app.get("/operations/metrics")
async def get_operations_metrics(
    request: Request, _: str = Depends(require_auth)
) -> dict[str, Any]:
    async with request.app.state.db_pool.acquire() as conn:
        durable = await conn.fetchrow(
            """
            SELECT COUNT(*) FILTER (WHERE job.status IN ('queued','running','retry'))::int AS active_jobs,
                   COUNT(*) FILTER (WHERE job.status='failed' AND job.finished_at > NOW()-INTERVAL '24 hours')::int AS failed_jobs_24h,
                   COUNT(*) FILTER (WHERE job.status='running' AND job.heartbeat_at < NOW()-INTERVAL '5 minutes')::int AS stalled_jobs,
                   AVG(EXTRACT(EPOCH FROM (job.finished_at-job.started_at)))
                       FILTER (WHERE job.status='completed') AS average_job_seconds
            FROM analysis_jobs job WHERE job.workspace_id=$1::uuid
            """,
            SETTINGS.workspace_id,
        )
        workers = await conn.fetchrow(
            """
            SELECT COUNT(DISTINCT lease_owner) FILTER (
                       WHERE status='running' AND heartbeat_at > NOW()-INTERVAL '5 minutes'
                   )::int AS active_worker_heartbeats,
                   COUNT(*) FILTER (WHERE status='running' AND workload_class='engine')::int AS active_engine_slots,
                   COUNT(*) FILTER (WHERE status='retry')::int AS retry_steps,
                   COUNT(*) FILTER (WHERE status='completed' AND workload_class='engine'
                                      AND result_json->>'cache_hit'='true')::int AS engine_cache_hits,
                   COUNT(*) FILTER (WHERE status='completed' AND workload_class='engine')::int AS engine_steps
            FROM analysis_job_steps WHERE workspace_id=$1::uuid
            """,
            SETTINGS.workspace_id,
        )
    stream_metrics: dict[str, Any] = {}
    for capability in ("orchestration", "engine", "ingest"):
        stream = SETTINGS.stream_for(capability)
        group_name = SETTINGS.consumer_group_for(capability)
        groups = await request.app.state.redis.xinfo_groups(stream)
        group = next((row for row in groups if row.get("name") == group_name), {})
        pending = await request.app.state.redis.xpending(stream, group_name)
        oldest = await request.app.state.redis.xpending_range(
            stream, group_name, min="-", max="+", count=1
        )
        stream_metrics[capability] = {
            "stream": stream,
            "lag": int(group.get("lag") or 0),
            "pending": int(pending.get("pending") or 0),
            "oldest_pending_idle_ms": (
                int(oldest[0].get("time_since_delivered") or 0) if oldest else None
            ),
            "dead_letters": int(
                await request.app.state.redis.xlen(SETTINGS.dead_letter_stream_for(capability))
            ),
        }
    worker_values = dict(workers or {})
    engine_steps = int(worker_values.get("engine_steps") or 0)
    cache_hits = int(worker_values.get("engine_cache_hits") or 0)
    return {
        "jobs": dict(durable or {}),
        "workers": worker_values,
        "engine_cache_hit_rate": cache_hits / engine_steps if engine_steps else None,
        "streams": stream_metrics,
    }


@app.post('/analysis/run/full', status_code=202, response_model=AnalysisRunResponse)
async def run_full_analysis(
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    job = await _enqueue_durable_job(
        request, job_type="full-analysis", workload_class="orchestration",
        step_type="full-analysis", idempotency_key=idempotency_key,
    )
    return _accepted_job_response(job)


@app.post('/analysis/run/engine-only', status_code=202, response_model=AnalysisRunResponse)
async def run_engine_only_analysis(
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    job = await _enqueue_durable_job(
        request, job_type="engine-only-analysis", workload_class="orchestration",
        step_type="engine-only-analysis", idempotency_key=idempotency_key,
    )
    return _accepted_job_response(job)


async def _enqueue_analysis_variant(
    request: Request, job_type: str, idempotency_key: str, payload: dict[str, Any] | None = None
) -> AnalysisRunResponse:
    job = await _enqueue_durable_job(
        request, job_type=job_type, workload_class="orchestration",
        step_type=job_type, idempotency_key=idempotency_key, payload=payload,
    )
    return _accepted_job_response(job)


@app.post('/analysis/run/incremental', status_code=202, response_model=AnalysisRunResponse)
async def run_incremental_analysis(
    request: Request, idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    return await _enqueue_analysis_variant(request, "incremental-analysis", idempotency_key)


@app.post('/analysis/run/line-matching', status_code=202, response_model=AnalysisRunResponse)
async def run_line_matching_reanalysis(
    request: Request, idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    return await _enqueue_analysis_variant(request, "line-matching-reanalysis", idempotency_key)


@app.post('/analysis/run/game-details', status_code=202, response_model=AnalysisRunResponse)
async def run_game_details_reanalysis(
    request: Request, idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    return await _enqueue_analysis_variant(request, "game-details-reanalysis", idempotency_key)


@app.post('/games/{game_id}/reanalyze', status_code=202, response_model=AnalysisRunResponse)
async def run_single_game_reanalysis(
    game_id: int, request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    return await _enqueue_analysis_variant(
        request, "per-game-reanalysis", idempotency_key, {"game_id": game_id}
    )


@app.post('/analysis/run/review-insights', status_code=202, response_model=AnalysisRunResponse)
async def run_review_insight_regeneration(
    request: Request, idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    return await _enqueue_analysis_variant(request, "review-insight-regeneration", idempotency_key)


@app.post('/analysis/run/fetch-games', status_code=202, response_model=AnalysisRunResponse)
async def run_fetch_games(
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    job = await _enqueue_durable_job(
        request, job_type="fetch-games", workload_class="ingest",
        step_type="provider-fetch", idempotency_key=idempotency_key,
    )
    return _accepted_job_response(job)


@app.post('/analysis/run/smoke-test', status_code=202, response_model=AnalysisRunResponse)
async def run_smoke_test(
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    job = await _enqueue_durable_job(
        request, job_type="smoke-analysis", workload_class="orchestration",
        step_type="smoke-analysis", idempotency_key=idempotency_key,
    )
    return _accepted_job_response(job)


@app.get('/analysis/status', response_model=AnalysisStatusResponse)
async def get_analysis_status(request: Request, _: str = Depends(require_auth)) -> AnalysisStatusResponse:
    async with request.app.state.db_pool.acquire() as conn:
        recent = await jobs.list_jobs(conn, limit=50)
    analysis_jobs = [job for job in recent if "analysis" in job["job_type"] or "reanalysis" in job["job_type"]]
    active = next((job for job in analysis_jobs if job["status"] in {"queued", "running", "retry"}), None)
    latest = analysis_jobs[0] if analysis_jobs else None
    completed = next((job for job in analysis_jobs if job["status"] == "completed"), None)
    if active:
        state = "running"
    elif latest and latest["status"] == "failed":
        state = "failed"
    elif latest and latest["status"] == "completed":
        state = "completed"
    else:
        state = "idle"
    updated = (latest or {}).get("updated_at") or datetime.now(timezone.utc)
    return AnalysisStatusResponse(
        state=state,
        active_job_id=active["job_id"] if active else None,
        active_run_type=active["job_type"] if active else None,
        last_completed_job_id=completed["job_id"] if completed else None,
        last_run_type=latest["job_type"] if latest else None,
        last_error=latest["error_detail"] if latest else None,
        updated_at=updated.isoformat(),
    )


@app.get('/analysis/progress', response_model=AnalysisProgressResponse)
async def get_analysis_progress(request: Request, _: str = Depends(require_auth)) -> AnalysisProgressResponse:
    async with request.app.state.db_pool.acquire() as conn:
        recent = await jobs.list_jobs(conn, limit=50)
    latest = next(
        (job for job in recent if "analysis" in job["job_type"] or "reanalysis" in job["job_type"]),
        None,
    )
    updated = latest["updated_at"] if latest else datetime.now(timezone.utc)
    return AnalysisProgressResponse(
        job_id=latest["job_id"] if latest else None,
        run_type=latest["job_type"] if latest else None,
        progress=latest["progress"] if latest else None,
        updated_at=updated.isoformat(),
    )


@app.get('/analysis/runs', response_model=AnalysisRunHistoryResponse)
async def get_analysis_runs(request: Request, limit: int = 10, _: str = Depends(require_auth)) -> AnalysisRunHistoryResponse:
    async with request.app.state.db_pool.acquire() as conn:
        recent = await jobs.list_jobs(conn, limit=min(max(limit * 3, 10), 100))
    entries: list[AnalysisRunHistoryEntry] = []
    for job in recent:
        if "analysis" not in job["job_type"] and "reanalysis" not in job["job_type"]:
            continue
        status = "completed" if job["status"] == "completed" else "failed" if job["status"] in {"failed", "cancelled"} else "running"
        entries.append(
            AnalysisRunHistoryEntry(
                run_id=job["job_id"], run_type=job["job_type"], status=status,
                started_at=(job["started_at"] or job["queued_at"]).isoformat(),
                finished_at=job["finished_at"].isoformat() if job["finished_at"] else None,
                error_reason=job["error_detail"],
            )
        )
        if len(entries) >= min(max(limit, 1), 50):
            break
    return AnalysisRunHistoryResponse(runs=entries)


@app.get('/auth/validate', response_model=AuthValidateResponse, responses={401: {"model": ErrorResponse}})
async def auth_validate(_: str = Depends(require_auth)) -> AuthValidateResponse:
    return AuthValidateResponse(ok=True, detail="Token is valid")


@app.get('/settings/runtime', response_model=RuntimeSettingsResponse, responses={401: {"model": ErrorResponse}})
async def get_runtime_settings(request: Request, _: str = Depends(require_auth)) -> RuntimeSettingsResponse:
    payload = await _load_postgres_runtime_settings(request.app.state.db_pool)
    return RuntimeSettingsResponse.model_validate(payload)


@app.put('/settings/runtime', response_model=RuntimeSettingsResponse, responses={401: {"model": ErrorResponse}, 422: {"model": ValidationErrorResponse}})
async def update_runtime_settings(request: Request, payload: dict[str, Any], _: str = Depends(require_auth)) -> RuntimeSettingsResponse:
    return await _save_postgres_runtime_settings(request.app.state.db_pool, payload)


@app.post('/repertoires/import', status_code=202, response_model=RepertoireImportResponse)
async def import_repertoires(
    request: Request,
    file: UploadFile = File(...),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> RepertoireImportResponse:
    payload = await file.read()
    if not payload:
        raise api_error(400, "EMPTY_UPLOAD", "Uploaded file is empty.")
    filename = file.filename or "upload.pgn"
    suffix = Path(filename).suffix.lower()
    if suffix == ".pgn":
        pgn_text = payload.decode("utf-8", errors="replace")
    elif suffix == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [name for name in archive.namelist() if Path(name).suffix.lower() == ".pgn"]
                if not members:
                    raise api_error(400, "INVALID_UPLOAD", "No PGN files were found in the archive.")
                pgn_text = "\n\n".join(
                    archive.read(name).decode("utf-8", errors="replace") for name in sorted(members)
                )
        except zipfile.BadZipFile as exc:
            raise api_error(400, "INVALID_UPLOAD", "Uploaded zip payload is invalid or corrupted.") from exc
    else:
        raise api_error(400, "INVALID_UPLOAD", "Upload a .zip archive of PGNs or a single .pgn file.")
    upload_hash = hashlib.sha256(pgn_text.encode("utf-8")).hexdigest()
    async with request.app.state.db_pool.acquire() as conn:
        async with conn.transaction():
            artifact_id = await conn.fetchval(
                """
                INSERT INTO source_artifacts(
                    id, workspace_id, source_type, provider, original_name,
                    content_hash, pgn_text, metadata_json
                ) VALUES (gen_random_uuid(), $1::uuid, 'repertoire', 'upload', $2, $3, $4, $5::jsonb)
                ON CONFLICT (workspace_id, source_type, content_hash) DO UPDATE
                SET updated_at = NOW()
                RETURNING id
                """,
                SETTINGS.workspace_id,
                filename,
                upload_hash,
                pgn_text,
                json.dumps({"uploaded_filename": filename, "archive": suffix == ".zip"}),
            )
            job, step, created = await jobs.create_job(
                conn,
                job_type="repertoire-import",
                workload_class="ingest",
                step_type="repertoire-import",
                request_payload={"source_artifact_id": str(artifact_id)},
                idempotency_key=idempotency_key,
            )
    if created:
        await enqueue_job(request.app.state.redis, "ingest", jobs.redis_message(step, "repertoire-import"))
    return RepertoireImportResponse(
        job_id=job["job_id"],
        status_url=f"/jobs/{job['job_id']}",
        status=job["status"],
        upload_hash=upload_hash,
        detail="Repertoire import queued.",
    )


@app.get('/repertoires/import-jobs/{job_id}', response_model=RepertoireImportJobResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def get_repertoire_import_job(
    job_id: str, request: Request, _: str = Depends(require_auth)
) -> RepertoireImportJobResponse:
    async with request.app.state.db_pool.acquire() as conn:
        job = await jobs.get_job(conn, job_id)
    if not job or job["job_type"] != "repertoire-import":
        raise api_error(404, "IMPORT_JOB_NOT_FOUND", "Repertoire import job was not found.")
    return RepertoireImportJobResponse(id=job["job_id"], status=job["status"], progress=job["progress"])


@app.post('/games/import', status_code=202, response_model=AnalysisRunResponse)
async def import_games(
    request: Request,
    file: UploadFile = File(...),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _: str = Depends(require_auth),
) -> AnalysisRunResponse:
    payload = await file.read()
    if not payload:
        raise api_error(400, "EMPTY_UPLOAD", "Uploaded file is empty.")
    filename = file.filename or "games.pgn"
    suffix = Path(filename).suffix.lower()
    if suffix == ".pgn":
        pgn_text = payload.decode("utf-8", errors="replace")
    elif suffix == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = [name for name in archive.namelist() if Path(name).suffix.lower() == ".pgn"]
                if not names:
                    raise api_error(400, "INVALID_UPLOAD", "No PGN files were found in the archive.")
                pgn_text = "\n\n".join(
                    archive.read(name).decode("utf-8", errors="replace") for name in sorted(names)
                )
        except zipfile.BadZipFile as exc:
            raise api_error(400, "INVALID_UPLOAD", "Uploaded zip payload is invalid or corrupted.") from exc
    else:
        raise api_error(400, "INVALID_UPLOAD", "Upload a .zip archive of PGNs or a single .pgn file.")
    content_hash = hashlib.sha256(pgn_text.encode("utf-8")).hexdigest()
    runtime = await db.fetch_runtime_settings(request.app.state.db_pool) or {}
    async with request.app.state.db_pool.acquire() as conn:
        async with conn.transaction():
            artifact_id = await conn.fetchval(
                """
                INSERT INTO source_artifacts(
                    id, workspace_id, source_type, provider, original_name,
                    content_hash, pgn_text, metadata_json
                ) VALUES (gen_random_uuid(), $1::uuid, 'game', 'upload', $2, $3, $4, $5::jsonb)
                ON CONFLICT (workspace_id, source_type, content_hash) DO UPDATE
                SET updated_at = NOW()
                RETURNING id
                """,
                SETTINGS.workspace_id,
                filename,
                content_hash,
                pgn_text,
                json.dumps({"uploaded_filename": filename, "archive": suffix == ".zip"}),
            )
            job, step, created = await jobs.create_job(
                conn,
                job_type="game-import",
                workload_class="ingest",
                step_type="game-import",
                request_payload={
                    "source_artifact_id": str(artifact_id),
                    "player_names": list(dict.fromkeys(
                        [
                            str(value) for value in [
                                runtime.get("player_name"), *(runtime.get("player_names") or [])
                            ] if value
                        ]
                    )),
                },
                idempotency_key=idempotency_key,
            )
    if created:
        await enqueue_job(request.app.state.redis, "ingest", jobs.redis_message(step, "game-import"))
    return _accepted_job_response(job, "Game import queued")


@app.post(
    "/sidelines",
    status_code=202,
    response_model=SidelineResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ValidationErrorResponse, "description": "Validation error"},
    },
)
async def create_sideline(
    payload: SidelineCreateRequest,
    request: Request,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        examples=["sideline-game-12345-ply-12-v1"],
        description="Client-generated key for deduplicating create requests.",
    ),
    principal: str = Depends(require_auth),
) -> SidelineResponse:
    request_id = str(uuid.uuid4())
    serialized_payload = payload.model_dump()

    async with request.app.state.db_pool.acquire() as conn:
        async with conn.transaction():
            job, step, created_job = await jobs.create_job(
                conn,
                job_type="sideline-analysis",
                workload_class="engine",
                step_type="sideline-analysis",
                request_payload=serialized_payload,
                idempotency_key=idempotency_key,
            )
            if created_job:
                await db.insert_sideline_request(
                    conn,
                    request_id=request_id,
                    game_id=payload.game_id,
                    move_ply=payload.move_ply,
                    requested_by=principal,
                    job_id=job["job_id"],
                    payload=serialized_payload,
                )
            else:
                existing = await db.fetch_by_idempotency_key(conn, idempotency_key)
                if existing is None:
                    raise api_error(
                        status_code=500,
                        error_code="IDEMPOTENCY_CONFLICT_RESOLUTION_FAILED",
                        detail="Idempotency key existed but record lookup failed",
                    )
                return to_response(existing)

    await enqueue_job(request.app.state.redis, "engine", jobs.redis_message(step, "sideline-analysis"))

    async with request.app.state.db_pool.acquire() as conn:
        created = await db.fetch_sideline_request(conn, request_id)
    if created is None:
        raise api_error(status_code=500, error_code="CREATE_LOOKUP_FAILED", detail="Created request was not found")
    return to_response(created)


@app.get(
    "/sidelines/{request_id}",
    response_model=SidelineResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Sideline request not found"},
    },
)
async def get_sideline(request_id: str, request: Request, _: str = Depends(require_auth)) -> SidelineResponse:
    async with request.app.state.db_pool.acquire() as conn:
        row = await db.fetch_sideline_request(conn, request_id)
    if row is None:
        raise api_error(status_code=404, error_code="NOT_FOUND", detail="Sideline request not found")
    return to_response(row)


@app.get(
    "/sidelines",
    response_model=list[SidelineResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ValidationErrorResponse, "description": "Validation error"},
    },
)
async def list_sidelines(request: Request, limit: int = 20, _: str = Depends(require_auth)) -> list[SidelineResponse]:
    bounded_limit = min(max(limit, 1), 100)
    async with request.app.state.db_pool.acquire() as conn:
        rows = await db.list_sideline_requests(conn, bounded_limit)
    return [to_response(row) for row in rows]


@app.get(
    "/games",
    response_model=list[GameOverviewResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ValidationErrorResponse, "description": "Validation error"},
    },
)
async def list_games(
    limit: int = 50,
    offset: int = 0,
    result: str | None = None,
    compliance: str | None = None,
    line_id: str | None = None,
    player: str | None = None,
    compliance_min: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    _: str = Depends(require_auth),
) -> list[GameOverviewResponse]:
    bounded_limit = min(max(limit, 1), 200)
    bounded_offset = max(offset, 0)
    normalized_sort_by = (sort_by or "date").lower()
    if normalized_sort_by not in {"date", "result", "compliance", "id"}:
        normalized_sort_by = "date"
    normalized_sort_dir = (sort_dir or "desc").lower()
    if normalized_sort_dir not in {"asc", "desc"}:
        normalized_sort_dir = "desc"
    rows = await fetch_games(
        limit=bounded_limit,
        offset=bounded_offset,
        result=result,
        compliance=compliance,
        line_id=line_id,
        player=player,
        compliance_min=compliance_min,
        date_from=date_from,
        date_to=date_to,
        sort_by=normalized_sort_by,
        sort_dir=normalized_sort_dir,
    )
    return [GameOverviewResponse(**row) for row in rows]


@app.get(
    "/games/{game_id}",
    response_model=GameDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Game not found"},
    },
)
async def get_game(game_id: int, _: str = Depends(require_auth)) -> GameDetailResponse:
    data = await fetch_game_detail(game_id)
    if data is None:
        raise api_error(status_code=404, error_code="NOT_FOUND", detail="Game not found")
    return GameDetailResponse(**data)


@app.get("/positions/{pos_id}/games")
async def get_position_games(
    pos_id: int,
    request: Request,
    uci_move: str | None = None,
    limit: int = 20,
    _: str = Depends(require_auth),
) -> list[dict[str, Any]]:
    async with request.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT game.id AS game_id, game.date, game.white, game.black, game.result,
                   game.player_color, gp.ply, gp.san_move, gp.uci_move,
                   match.matched_line_id AS line_id, match.compliance
            FROM game_positions gp
            JOIN games game ON game.workspace_id=gp.workspace_id AND game.id=gp.game_id
            LEFT JOIN workspace_state state ON state.workspace_id=gp.workspace_id
            LEFT JOIN matches match ON match.workspace_id=gp.workspace_id
                                   AND match.game_id=gp.game_id
                                   AND match.analysis_run_id=state.active_analysis_run_id
            WHERE gp.workspace_id=$1::uuid AND gp.pos_id=$2
              AND ($3::text IS NULL OR gp.uci_move=$3)
            ORDER BY game.date DESC NULLS LAST, game.id DESC, gp.ply
            LIMIT $4
            """,
            SETTINGS.workspace_id, pos_id, uci_move, min(max(limit, 1), 200),
        )
    return [dict(row) for row in rows]


@app.get("/statistics/months")
async def get_month_statistics(
    request: Request, _: str = Depends(require_auth)
) -> list[dict[str, Any]]:
    async with request.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT substring(replace(game.date, '.', '-') FROM 1 FOR 7) AS key,
                   COUNT(DISTINCT game.id)::int AS total_games,
                   AVG(gp.time_spent_seconds) FILTER (
                       WHERE COALESCE(ap.repertoire_class, gp.repertoire_class)
                             IN ('IN_REPERTOIRE_MAIN','IN_REPERTOIRE_OTHER')
                   ) AS in_book_avg,
                   AVG(gp.time_spent_seconds) FILTER (
                       WHERE COALESCE(ap.repertoire_class, gp.repertoire_class)='OUT_OF_REPERTOIRE'
                   ) AS out_book_avg,
                   AVG(gp.time_spent_fraction) FILTER (
                       WHERE COALESCE(ap.repertoire_class, gp.repertoire_class)
                             IN ('IN_REPERTOIRE_MAIN','IN_REPERTOIRE_OTHER')
                   ) AS in_book_frac_avg,
                   AVG(gp.time_spent_fraction) FILTER (
                       WHERE COALESCE(ap.repertoire_class, gp.repertoire_class)='OUT_OF_REPERTOIRE'
                   ) AS out_book_frac_avg
            FROM games game
            JOIN game_positions gp ON gp.workspace_id=game.workspace_id AND gp.game_id=game.id
            LEFT JOIN workspace_state state ON state.workspace_id=gp.workspace_id
            LEFT JOIN analysis_ply ap ON ap.workspace_id=gp.workspace_id
                                     AND ap.game_id=gp.game_id AND ap.ply=gp.ply
                                     AND ap.analysis_run_id=state.active_analysis_run_id
            WHERE game.workspace_id=$1::uuid AND game.is_daily=0 AND game.date IS NOT NULL
            GROUP BY substring(replace(game.date, '.', '-') FROM 1 FOR 7)
            ORDER BY key DESC
            """,
            SETTINGS.workspace_id,
        )
    return [dict(row) for row in rows]


@app.get("/time-patterns/summary")
async def get_time_pattern_summary(
    request: Request, _: str = Depends(require_auth)
) -> dict[str, int]:
    async with request.app.state.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(pattern.slow_in_book), 0)::int AS slow_in_book,
                   COALESCE(SUM(pattern.instant_out_of_book), 0)::int AS instant_out_of_book,
                   COALESCE(SUM(pattern.blunder_cluster), 0)::int AS blunder_cluster
            FROM workspace_state state
            LEFT JOIN time_patterns pattern
              ON pattern.workspace_id=state.workspace_id
             AND pattern.analysis_run_id=state.active_analysis_run_id
            WHERE state.workspace_id=$1::uuid
            """,
            SETTINGS.workspace_id,
        )
    return dict(row) if row else {
        "slow_in_book": 0, "instant_out_of_book": 0, "blunder_cluster": 0,
    }


@app.get("/overview/summary", response_model=dict[str, Any])
async def get_overview_summary(_: str = Depends(require_auth)) -> dict[str, Any]:
    try:
        return await fetch_overview_summary()
    except Exception:
        logger.exception("Overview summary query failed")
        raise


@app.get("/lines/stats", response_model=list[dict[str, Any]])
async def get_lines_stats(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_lines_stats()


@app.get("/lines/stats/{line_id}", response_model=dict[str, Any])
async def get_line_stats_detail(line_id: str, _: str = Depends(require_auth)) -> dict[str, Any]:
    detail = await fetch_line_stats_detail(line_id)
    if detail is None:
        raise api_error(status_code=404, error_code="NOT_FOUND", detail="Line stats not found")
    return detail


@app.get("/lines/stats/{line_id}/history", response_model=dict[str, Any])
async def get_line_stats_history(line_id: str, _: str = Depends(require_auth)) -> dict[str, Any]:
    return await fetch_line_stats_history(line_id)


@app.get("/time-usage/stats", response_model=TimeUsageStatsResponse)
async def get_time_usage_stats(
    pivot: Literal["self_vs_opp", "in_book_vs_out_of_book"],
    _: str = Depends(require_auth),
) -> TimeUsageStatsResponse:
    payload = await fetch_time_usage_stats(pivot)
    return TimeUsageStatsResponse(**payload)


@app.get("/rating-bands/stats", response_model=RatingBandStatsResponse)
async def get_rating_band_stats(band_size: int = 100, _: str = Depends(require_auth)) -> RatingBandStatsResponse:
    payload = await fetch_rating_band_stats_payload(band_size)
    payload["band_size"] = normalize_rating_band_size(int(payload.get("band_size", band_size)))
    payload["allowed_band_sizes"] = ALLOWED_RATING_BAND_SIZES
    return RatingBandStatsResponse(**payload)


@app.get("/insights", response_model=list[dict[str, Any]])
async def list_insights(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_insights()


@app.get("/review/items", response_model=list[dict[str, Any]])
async def list_review_items(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_review_items()


async def _fetch_lines_tree_contract_payload(pos_id: int, my_side_only: bool, request: Request) -> dict[str, Any]:
    repertoire_rows = await _fetch_tree_repertoire_children_backend(pos_id, my_side_only, request)
    game_rows = await _fetch_tree_game_children_backend(pos_id, my_side_only, request)
    return build_tree_contract_payload(
        pos_id=pos_id,
        my_side_only=my_side_only,
        repertoire_rows=repertoire_rows,
        game_rows=game_rows,
    )


async def _fetch_position_intelligence_payload(pos_id: int, my_side_only: bool, request: Request) -> dict[str, Any]:
    repertoire_rows = await _fetch_tree_repertoire_children_backend(pos_id, my_side_only, request)
    game_rows = await _fetch_tree_game_children_backend(pos_id, my_side_only, request)
    summary = await _fetch_position_intelligence_summary_backend(pos_id, request)
    return build_position_intelligence_payload(
        pos_id=pos_id,
        my_side_only=my_side_only,
        repertoire_rows=repertoire_rows,
        game_rows=game_rows,
        summary=summary,
    )


@app.get("/lines/tree/browse", response_model=TreeBrowseResponse)
async def get_lines_tree_browse(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeBrowseResponse:
    payload = await _fetch_lines_tree_contract_payload(pos_id, my_side_only, request)
    return TreeBrowseResponse(**payload)


@app.get("/lines/tree/coverage", response_model=TreeCoverageResponse)
async def get_lines_tree_coverage(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeCoverageResponse:
    payload = await _fetch_lines_tree_contract_payload(pos_id, my_side_only, request)
    return TreeCoverageResponse(**payload)


@app.get("/lines/tree/branch-metrics", response_model=TreeBranchMetricsResponse)
async def get_lines_tree_branch_metrics(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeBranchMetricsResponse:
    payload = await _fetch_lines_tree_contract_payload(pos_id, my_side_only, request)
    return TreeBranchMetricsResponse(**payload)


@app.get("/positions/{pos_id}/intelligence", response_model=PositionIntelligenceResponse)
async def get_position_intelligence(
    pos_id: int,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> PositionIntelligenceResponse:
    payload = await _fetch_position_intelligence_payload(pos_id, my_side_only, request)
    return PositionIntelligenceResponse(**payload)


@app.get("/positions/by-fen/lookup")
async def lookup_position(fen: str, request: Request, _: str = Depends(require_auth)) -> dict[str, int] | None:
    async with request.app.state.db_pool.acquire() as conn:
        pos_id = await conn.fetchval("SELECT id FROM positions WHERE fen_norm = $1", fen)
    return {"pos_id": int(pos_id)} if pos_id is not None else None


@app.get("/lines/{line_id}/moves")
async def get_line_moves_api(
    line_id: str, request: Request, max_ply: int | None = None,
    _: str = Depends(require_auth),
) -> list[dict[str, Any]]:
    async with request.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ply, pos_id, san_move, uci_move, next_pos_id
            FROM line_positions
            WHERE workspace_id = $1::uuid AND line_id = $2
              AND ($3::int IS NULL OR ply <= $3)
            ORDER BY ply
            """,
            SETTINGS.workspace_id, line_id, max_ply,
        )
    return [dict(row) for row in rows]


@app.post("/positions/{pos_id}/mainline")
async def set_mainline_override(
    pos_id: int, payload: MainlineOverrideRequest, request: Request,
    _: str = Depends(require_auth),
) -> dict[str, Any]:
    async with request.app.state.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_mainline_overrides(workspace_id, pos_id, uci_move, next_pos_id, updated_at)
            VALUES ($1::uuid, $2, $3, $4, NOW())
            ON CONFLICT (workspace_id, pos_id) DO UPDATE
            SET uci_move=EXCLUDED.uci_move, next_pos_id=EXCLUDED.next_pos_id, updated_at=NOW()
            """,
            SETTINGS.workspace_id, pos_id, payload.uci_move, payload.next_pos_id,
        )
    return {"pos_id": pos_id, "uci_move": payload.uci_move, "next_pos_id": payload.next_pos_id}


@app.get("/tree/explorer", response_model=TreeCoverageResponse, deprecated=True)
async def get_tree_explorer_legacy(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeCoverageResponse:
    payload = await _fetch_lines_tree_contract_payload(pos_id, my_side_only, request)
    return TreeCoverageResponse(**payload)


def _require_postgres_trainer_sessions() -> None:
    return None


def _trainer_player_moves_for_side(line_moves: list[dict[str, Any]], side_to_play: str) -> list[dict[str, Any]]:
    player_is_white = (side_to_play or "white").lower() != "black"
    return [
        move
        for move in line_moves
        if (int(move.get("ply") or 0) % 2 == 1) == player_is_white
    ]


def _trainer_difficulty(line_info: dict[str, Any]) -> Literal["easy", "medium", "hard"]:
    if int(line_info.get("needs_review") or 0) == 1:
        return "hard"
    streak = int(line_info.get("correct_streak") or 0)
    if streak >= 3:
        return "easy"
    return "medium"


async def _ensure_trainer_state_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO trainer_line_state (workspace_id, line_id, side_to_play)
        SELECT workspace_id, line_id, COALESCE(side_to_play, 'white')
        FROM repertoire_lines
        WHERE workspace_id = $1::uuid
        ON CONFLICT (workspace_id, line_id) DO NOTHING
        """,
        SETTINGS.workspace_id,
    )
    await conn.execute(
        """
        UPDATE trainer_line_state tls
        SET side_to_play = COALESCE(rl.side_to_play, 'white')
        FROM repertoire_lines rl
        WHERE rl.workspace_id = tls.workspace_id AND rl.line_id = tls.line_id
          AND tls.workspace_id = $1::uuid
        """,
        SETTINGS.workspace_id,
    )


async def _fetch_trainer_line_info_postgres(conn: asyncpg.Connection, line_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT rl.line_id, rl.side_to_play, rl.is_priority,
               tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
               tls.auto_priority_score, tls.focus_max_ply
        FROM repertoire_lines rl
        JOIN trainer_line_state tls ON rl.workspace_id = tls.workspace_id AND rl.line_id = tls.line_id
        WHERE rl.line_id = $1 AND rl.workspace_id = $2::uuid
        """,
        line_id,
        SETTINGS.workspace_id,
    )
    return dict(row) if row else None


async def _fetch_line_moves_postgres(conn: asyncpg.Connection, line_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT lp.ply, lp.san_move, lp.uci_move, lp.pos_id, lp.next_pos_id, COALESCE(p.fen_norm, '') AS fen
        FROM line_positions lp
        LEFT JOIN positions p ON p.id = lp.pos_id
        WHERE lp.line_id = $1 AND lp.workspace_id = $2::uuid
        ORDER BY lp.ply
        """,
        line_id,
        SETTINGS.workspace_id,
    )
    return [dict(row) for row in rows]


async def _trainer_queue_snapshot_postgres(conn: asyncpg.Connection) -> TrainerQueueSnapshot:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE learned = 0) AS remaining,
            COUNT(*) FILTER (WHERE learned = 1) AS learned,
            COUNT(*) FILTER (WHERE needs_review = 1) AS needs_review
        FROM trainer_line_state
        WHERE workspace_id = $1::uuid
        """,
        SETTINGS.workspace_id,
    )
    if not row:
        return TrainerQueueSnapshot(remaining=0, learned=0, needs_review=0)
    return TrainerQueueSnapshot(
        remaining=int(row["remaining"] or 0),
        learned=int(row["learned"] or 0),
        needs_review=int(row["needs_review"] or 0),
    )


async def _trainer_item_postgres(conn: asyncpg.Connection, line_id: str, player_idx: int) -> TrainerSessionItem | None:
    line_info = await _fetch_trainer_line_info_postgres(conn, line_id)
    if not line_info:
        return None
    line_moves = await _fetch_line_moves_postgres(conn, line_id)
    player_moves = _trainer_player_moves_for_side(line_moves, str(line_info.get("side_to_play") or "white"))
    if player_idx >= len(player_moves):
        return None
    move = player_moves[player_idx]
    expected_move_uci = str(move.get("uci_move") or "")
    return TrainerSessionItem(
        branch_id=line_id,
        fen=str(move.get("fen") or ""),
        prompt=f"Find the repertoire move for {line_info.get('side_to_play', 'white')}.",
        expected_move_uci=expected_move_uci,
        difficulty=_trainer_difficulty(line_info),
    )


@app.post("/trainer/sessions", response_model=TrainerSessionResponse)
async def create_trainer_session(payload: TrainerSessionCreateRequest, request: Request, _: str = Depends(require_auth)) -> TrainerSessionResponse:
    _require_postgres_trainer_sessions()

    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)

        line_id = payload.line_id
        if not line_id:
            row = await conn.fetchrow(
                """
                SELECT rl.line_id
                FROM repertoire_lines rl
                JOIN trainer_line_state tls ON rl.line_id = tls.line_id
                WHERE rl.workspace_id = tls.workspace_id
                  AND rl.workspace_id = $2::uuid AND tls.learned = $1
                ORDER BY rl.line_id
                LIMIT 1
                """,
                1 if payload.mode == "review" else 0,
                SETTINGS.workspace_id,
            )
            if not row:
                raise api_error(404, "NOT_FOUND", "No trainer lines available for mode")
            line_id = str(row["line_id"])

        line_info = await _fetch_trainer_line_info_postgres(conn, line_id)
        if not line_info:
            raise api_error(404, "NOT_FOUND", "Line not found in trainer state")

        item = await _trainer_item_postgres(conn, line_id, 0)
        if not item:
            raise api_error(409, "CONFLICT", "Line has no trainable player moves")

        session_id = str(uuid.uuid4())
        session_row = await conn.fetchrow(
            """
            INSERT INTO trainer_sessions (id, workspace_id, line_id, mode, player_move_index, had_incorrect, completed)
            VALUES ($1::uuid, $4::uuid, $2, $3, 0, 0, 0)
            RETURNING id
            """,
            session_id,
            line_id,
            payload.mode,
            SETTINGS.workspace_id,
        )
        if not session_row:
            raise api_error(500, "INTERNAL_ERROR", "Failed to create trainer session")

        return TrainerSessionResponse(
            session_id=str(session_row["id"]),
            item=item,
            queue_snapshot=await _trainer_queue_snapshot_postgres(conn),
        )


@app.post("/trainer/sessions/{session_id}/answer", response_model=TrainerSessionAnswerResponse)
async def answer_trainer_session(session_id: str, payload: TrainerSessionAnswerRequest, request: Request, _: str = Depends(require_auth)) -> TrainerSessionAnswerResponse:
    _require_postgres_trainer_sessions()

    try:
        normalized_session_id = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise api_error(400, "INVALID_SESSION_ID", "Session id must be a valid UUID") from exc

    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)
        session = await conn.fetchrow(
            """
            SELECT id, line_id, mode, player_move_index, had_incorrect, completed
            FROM trainer_sessions
            WHERE id = $1::uuid AND workspace_id = $2::uuid
            """,
            normalized_session_id,
            SETTINGS.workspace_id,
        )
        if not session:
            raise api_error(404, "NOT_FOUND", "Trainer session not found")

        session_data = dict(session)
        if int(session_data.get("completed") or 0) == 1:
            raise api_error(409, "CONFLICT", "Trainer session already completed")

        line_info = await _fetch_trainer_line_info_postgres(conn, str(session_data["line_id"]))
        if not line_info:
            raise api_error(404, "NOT_FOUND", "Line not found in trainer state")

        line_moves = await _fetch_line_moves_postgres(conn, str(session_data["line_id"]))
        player_moves = _trainer_player_moves_for_side(line_moves, str(line_info.get("side_to_play") or "white"))

        player_idx = int(session_data.get("player_move_index") or 0)
        if player_idx >= len(player_moves):
            raise api_error(409, "CONFLICT", "Trainer session already completed")

        expected_move = str(player_moves[player_idx].get("uci_move") or "")
        is_correct = payload.move_uci == expected_move
        prior_streak = int(line_info.get("correct_streak") or 0)
        had_incorrect = int(session_data.get("had_incorrect") or 0)

        if is_correct:
            player_idx += 1
            completed = 1 if player_idx >= len(player_moves) else 0
            grade: Literal["again", "hard", "good", "easy"] = "easy" if completed else "good"
            streak_delta = 1 if completed else 0
            await conn.execute(
                """
                UPDATE trainer_line_state
                SET learned = 1,
                    needs_review = 0,
                    correct_streak = CASE WHEN $2 THEN correct_streak + 1 ELSE correct_streak END,
                    times_correct = CASE WHEN $2 THEN times_correct + 1 ELSE times_correct END,
                    last_seen = $3
                WHERE line_id = $1 AND workspace_id = $4::uuid
                """,
                str(session_data["line_id"]),
                completed == 1,
                datetime.now(timezone.utc).isoformat(),
                SETTINGS.workspace_id,
            )
        else:
            had_incorrect = 1
            completed = 0
            grade = "again"
            streak_delta = -prior_streak if prior_streak > 0 else 0
            await conn.execute(
                """
                UPDATE trainer_line_state
                SET needs_review = 1,
                    correct_streak = 0,
                    times_incorrect = times_incorrect + 1,
                    last_seen = $2
                WHERE line_id = $1 AND workspace_id = $3::uuid
                """,
                str(session_data["line_id"]),
                datetime.now(timezone.utc).isoformat(),
                SETTINGS.workspace_id,
            )

        await conn.execute(
            """
            UPDATE trainer_sessions
            SET player_move_index = $2,
                had_incorrect = $3,
                completed = $4,
                updated_at = NOW()
            WHERE id = $1::uuid AND workspace_id = $5::uuid
            """,
            normalized_session_id,
            player_idx,
            had_incorrect,
            completed,
            SETTINGS.workspace_id,
        )

        state_row = await conn.fetchrow(
            """
            SELECT learned, needs_review
            FROM trainer_line_state
            WHERE line_id = $1 AND workspace_id = $2::uuid
            """,
            str(session_data["line_id"]),
            SETTINGS.workspace_id,
        )
        if not state_row:
            raise api_error(404, "NOT_FOUND", "Line not found after trainer session answer")

        item_state: Literal["learned", "needs_review"] = "needs_review" if int(state_row["needs_review"] or 0) == 1 else "learned"
        next_item = None if completed else await _trainer_item_postgres(conn, str(session_data["line_id"]), player_idx)
        remediation = None
        if not is_correct:
            remediation = TrainerSessionRemediation(
                best_move_uci=expected_move,
                principal_variation=[expected_move],
                explanation_markdown="The submitted move does not match the expected repertoire continuation.",
                retry_required=True,
            )

        return TrainerSessionAnswerResponse(
            outcome="correct" if is_correct else "incorrect",
            grade=grade,
            streak_delta=streak_delta,
            item_state=item_state,
            next_item=next_item,
            remediation=remediation,
        )


@app.get("/trainer/queue", response_model=TrainerQueueResponse)
async def get_trainer_queue(
    request: Request,
    mode: Literal["learn", "review"] = "review",
    _: str = Depends(require_auth),
) -> TrainerQueueResponse:
    learned_only = mode == "review"

    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)
        rows = await conn.fetch(
            """
            SELECT rl.line_id, rl.is_priority, rl.side_to_play,
                   tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
                   tls.auto_priority_score, tls.focus_max_ply
            FROM repertoire_lines rl
            JOIN trainer_line_state tls
              ON rl.workspace_id = tls.workspace_id AND rl.line_id = tls.line_id
            WHERE rl.workspace_id = $1::uuid AND tls.learned = $2
            """,
            SETTINGS.workspace_id,
            1 if learned_only else 0,
        )
    return TrainerQueueResponse(mode=mode, items=[TrainerQueueEntry(**dict(row)) for row in rows])


@app.post("/trainer/outcomes", response_model=TrainerOutcomeResponse)
async def post_trainer_outcome(
    payload: TrainerOutcomeRequest,
    request: Request,
    _: str = Depends(require_auth),
) -> TrainerOutcomeResponse:
    resolved_is_correct = payload.is_correct
    if resolved_is_correct is None and payload.outcome is not None:
        resolved_is_correct = payload.outcome == "correct"
    if resolved_is_correct is None and payload.grade is not None:
        resolved_is_correct = payload.grade != "again"
    if resolved_is_correct is None:
        raise api_error(400, "INVALID_INPUT", "Expected is_correct, outcome, or grade")

    if payload.outcome is not None and resolved_is_correct != (payload.outcome == "correct"):
        raise api_error(400, "INVALID_INPUT", "outcome conflicts with is_correct")
    if payload.grade is not None and (payload.grade == "again") != (resolved_is_correct is False):
        raise api_error(400, "INVALID_INPUT", "grade conflicts with resolved correctness")

    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)
        info = await _fetch_trainer_line_info_postgres(conn, payload.line_id)
        if not info:
            raise api_error(404, "NOT_FOUND", "Line not found in trainer state")

        current_streak = int(info.get("correct_streak") or 0)
        now_iso = datetime.now(timezone.utc).isoformat()
        if resolved_is_correct:
            await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET learned = COALESCE($2, learned),
                        needs_review = 0,
                        correct_streak = $3,
                        times_correct = times_correct + 1,
                        last_seen = $4
                    WHERE line_id = $1 AND workspace_id = $5::uuid
                    """,
                    payload.line_id,
                    1 if payload.mode == "learn" else None,
                    current_streak + 1,
                    now_iso,
                    SETTINGS.workspace_id,
            )
        else:
            await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET needs_review = 1,
                        correct_streak = 0,
                        times_incorrect = times_incorrect + 1,
                        last_seen = $2
                    WHERE line_id = $1 AND workspace_id = $3::uuid
                    """,
                    payload.line_id,
                    now_iso,
                    SETTINGS.workspace_id,
            )

        row = await conn.fetchrow(
                """
                SELECT line_id, learned, needs_review, correct_streak, times_correct, times_incorrect
                FROM trainer_line_state
                WHERE line_id = $1 AND workspace_id = $2::uuid
                """,
                payload.line_id,
                SETTINGS.workspace_id,
        )
        if not row:
            raise api_error(404, "NOT_FOUND", "Line not found after update")
        return TrainerOutcomeResponse(**dict(row))


@app.post("/trainer/priority-override", response_model=TrainerQueueEntry)
async def set_trainer_priority_override(
    payload: TrainerPriorityOverrideRequest,
    request: Request,
    _: str = Depends(require_auth),
) -> TrainerQueueEntry:
    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)
        await conn.execute(
                """
                UPDATE trainer_line_state
                SET priority_override = $2
                WHERE line_id = $1 AND workspace_id = $3::uuid
                """,
                payload.line_id,
                int(payload.value),
                SETTINGS.workspace_id,
        )
        row = await _fetch_trainer_line_info_postgres(conn, payload.line_id)
        if not row:
            raise api_error(404, "NOT_FOUND", "Line not found in trainer state")
        return TrainerQueueEntry(**row)


@app.delete("/trainer/lines/{line_id}")
async def discard_trainer_line_api(
    line_id: str, request: Request, _: str = Depends(require_auth)
) -> dict[str, Any]:
    async with request.app.state.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM repertoire_lines WHERE workspace_id=$1::uuid AND line_id=$2",
            SETTINGS.workspace_id, line_id,
        )
    if result.endswith("0"):
        raise api_error(404, "NOT_FOUND", "Repertoire line was not found.")
    return {"removed": True, "line_id": line_id}


@app.get("/review/actions", response_model=list[ReviewPropositionResponse])
async def list_review_actions(
    status: Literal["pending", "approved", "disapproved", "all"] = "pending",
    request: Request = None,
    _: str = Depends(require_auth),
) -> list[ReviewPropositionResponse]:
    rows = await _fetch_review_propositions_backend(status, request)
    return [ReviewPropositionResponse(**row) for row in rows]


@app.get("/review/actions/{proposition_id}", response_model=ReviewPropositionDetailResponse)
async def get_review_action(
    proposition_id: int,
    request: Request = None,
    _: str = Depends(require_auth),
) -> ReviewPropositionDetailResponse:
    detail = await _fetch_review_proposition_detail_backend(proposition_id, request)
    if not detail:
        raise api_error(404, "NOT_FOUND", "Proposition not found.")
    return ReviewPropositionDetailResponse(**detail)


@app.get("/review/branch-queue", response_model=list[BranchQueueEntryResponse])
async def list_review_branch_queue(
    request: Request = None,
    _: str = Depends(require_auth),
) -> list[BranchQueueEntryResponse]:
    rows = await _fetch_branch_queue_backend(request)
    return [BranchQueueEntryResponse(**row) for row in rows]


@app.post("/review/actions", response_model=ReviewActionResponse)
async def execute_review_action(
    payload: ReviewActionRequest,
    request: Request = None,
    _: str = Depends(require_auth),
) -> ReviewActionResponse:
    result = await _execute_review_action_backend(payload.proposition_id, payload.action, request)
    if not result.get("success"):
        raise api_error(404, "NOT_FOUND", str(result.get("message") or "Review action failed."))

    return ReviewActionResponse(
        success=True,
        message=str(result.get("message") or ""),
        proposition=ReviewPropositionDetailResponse(**result["proposition"]) if result.get("proposition") else None,
        status_change=ReviewActionDelta(**result["status_change"]) if result.get("status_change") else None,
        queue_change=ReviewActionDelta(**result["queue_change"]) if result.get("queue_change") else None,
        queue_delta=ReviewQueueDelta(**result["queue_delta"]) if result.get("queue_delta") else None,
        priority_change=ReviewPriorityDelta(**result["priority_change"]) if result.get("priority_change") else None,
    )
