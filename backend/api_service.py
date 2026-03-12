from __future__ import annotations

import uuid
import threading
import configparser
import asyncio
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from datetime import timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Literal

import asyncpg
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend import db
from backend import repertoire_import
from backend.queue import enqueue_job, ensure_consumer_group, redis_client
from backend.read_api import (
    fetch_game_detail,
    fetch_games,
    fetch_insights,
    fetch_lines_stats,
    fetch_overview_summary,
    fetch_rating_band_stats,
    fetch_review_items,
    fetch_time_usage_stats,
)
from backend.settings import SETTINGS
from analysis import game_fetcher
from analysis import pipeline as analysis_pipeline
from analysis import smoke_test as smoke_test_module
from storage import database, queries


BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_INI_PATH = BASE_DIR / "config" / "settings.ini"


@dataclass
class RuntimeConfig:
    repertoire_dir: str
    games_dir: str
    database_path: str
    stockfish_path: str
    piece_dir: str
    engine_depth: int
    max_plies: int
    player_name: str
    player_names: list[str]
    rating_band_size: int
    matching_mode: str
    enable_engine_cache: bool
    incremental_analysis: bool
    review_top_n: int
    tabiya_top_n: int
    engine_workers: int
    engine_worker_cap: int
    engine_threads: int
    engine_hash_mb: int
    engine_mode: str
    engine_max_time_ms: int
    engine_profile: str
    engine_cache_prune_non_active: bool
    missing_coverage_proposal_threshold: int
    chesscom_usernames: list[str]
    lichess_usernames: list[str]
    fetch_variants: list[str]
    fetch_days_back: int


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
    header: dict[str, Any]
    moves: list[GameMoveResponse]
    prev_game_id: int | None = None
    next_game_id: int | None = None


class AnalysisRunResponse(BaseModel):
    accepted: bool
    detail: str
    job_id: str
    run_type: str


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
    job_id: str
    run_type: str
    state: Literal["running", "completed", "failed"]
    started_at: str
    finished_at: str | None = None
    error: str | None = None


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
    total_repertoire_moves: int
    covered_by_games: int
    coverage_pct: float


class TreeBranchMetricsResponse(BaseModel):
    pos_id: int
    top_repertoire_branches: list[dict[str, Any]]
    top_game_branches: list[dict[str, Any]]


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
    is_correct: bool
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




class TrainerSessionCreateRequest(BaseModel):
    mode: Literal["learn", "review"] = "review"
    line_id: str | None = None


class TrainerSessionNextStep(BaseModel):
    phase: Literal["prompt", "user_attempt", "reveal_explanation", "grading", "next_item_transition", "completed"]
    expected_move_uci: str | None = None
    explanation: str | None = None


class TrainerSessionResponse(BaseModel):
    session_id: str
    line_id: str
    mode: Literal["learn", "review"]
    player_move_index: int
    expected_move_uci: str | None = None
    completed: bool
    next_step: TrainerSessionNextStep


class TrainerSessionAnswerRequest(BaseModel):
    answer_uci: str = Field(min_length=4)


class TrainerSessionAnswerResponse(BaseModel):
    session_id: str
    line_id: str
    mode: Literal["learn", "review"]
    answer_uci: str
    expected_move_uci: str | None
    is_correct: bool
    feedback: str
    learned: int
    needs_review: int
    correct_streak: int
    times_correct: int
    times_incorrect: int
    completed: bool
    next_step: TrainerSessionNextStep

class ReviewPropositionResponse(BaseModel):
    id: int
    proposition_type: str
    status: str
    evidence_count: int
    threshold_count: int
    pos_id: int
    uci_move: str
    line_id_hint: str | None = None
    updated_at: str


class ReviewPropositionDetailResponse(ReviewPropositionResponse):
    proposition_key: str
    dismissed_count: int | None = None
    detail: dict[str, Any] | None = None
    created_at: str | None = None
    decided_at: str | None = None


class BranchQueueEntryResponse(BaseModel):
    proposition_id: int
    queue_status: str
    queued_at: str | None = None
    proposition_status: str
    evidence_count: int
    threshold_count: int
    pos_id: int
    uci_move: str
    line_id_hint: str | None = None
    updated_at: str


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
    priority_change: ReviewPriorityDelta | None = None


class AuthValidateResponse(BaseModel):
    ok: bool
    detail: str


class RuntimeSettingsResponse(BaseModel):
    chesscom_usernames: list[str]
    lichess_usernames: list[str]
    variants: list[str]
    days_back: int = Field(ge=1)
    games_dir: str | None = None
    database_path: str | None = None
    repertoire_dir: str | None = None
    stockfish_path: str | None = None
    piece_dir: str | None = None
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
    engine_workers: int | None = None
    engine_worker_cap: int | None = None
    engine_threads: int | None = None
    engine_hash_mb: int | None = None
    engine_mode: str | None = None
    engine_max_time_ms: int | None = None
    engine_profile: str | None = None
    engine_cache_prune_non_active: bool | None = None
    missing_coverage_proposal_threshold: int | None = None


class RuntimeSettingsUpdateRequest(BaseModel):
    chesscom_usernames: list[str] = Field(default_factory=list)
    lichess_usernames: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    days_back: int = Field(ge=1, le=3650)
    repertoire_dir: str | None = None
    games_dir: str | None = None
    database_path: str | None = None
    stockfish_path: str | None = None
    piece_dir: str | None = None
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
    engine_workers: int | None = Field(default=None, ge=1)
    engine_worker_cap: int | None = Field(default=None, ge=1)
    engine_threads: int | None = Field(default=None, ge=1)
    engine_hash_mb: int | None = Field(default=None, ge=1)
    engine_mode: str | None = None
    engine_max_time_ms: int | None = Field(default=None, ge=1)
    engine_profile: str | None = None
    engine_cache_prune_non_active: bool | None = None
    missing_coverage_proposal_threshold: int | None = Field(default=None, ge=1)






class RepertoireImportResponse(BaseModel):
    job_id: str
    status: Literal["completed"]
    upload_hash: str
    inserted_lines: int
    duplicate_lines: int
    total_lines: int
    detail: str


class RepertoireImportJobResponse(BaseModel):
    id: str
    status: Literal["completed"]
    progress: dict[str, Any]

def _sqlite_runtime_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SETTINGS.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


async def _with_sqlite(fn, *args, **kwargs):
    if SETTINGS.data_backend == "postgres":
        raise api_error(
            status_code=501,
            error_code="NOT_IMPLEMENTED",
            detail=(
                "This endpoint is currently implemented for SQLite data backend. "
                "Postgres parity is not yet implemented for trainer/stateful line endpoints."
            ),
        )

    def runner():
        with _sqlite_runtime_conn() as conn:
            return fn(conn, *args, **kwargs)

    return await asyncio.to_thread(runner)


def _require_postgres_request(request: Request | None) -> Request:
    if request is None:
        raise api_error(500, "INTERNAL_ERROR", "Request context is required for PostgreSQL backend access.")
    return request


async def _fetch_tree_repertoire_children_backend(
    pos_id: int,
    my_side_only: bool,
    request: Request | None,
) -> list[dict[str, Any]]:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.fetch_tree_repertoire_children, pos_id, my_side_only=my_side_only)

    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH repertoire_rows AS (
                SELECT lp.uci_move,
                       MIN(lp.san_move) AS san_move,
                       lp.next_pos_id,
                       COUNT(*)::int AS weight,
                       MAX(CASE WHEN rl.is_priority = 1 THEN 1 ELSE 0 END)::int AS is_priority_edge,
                       MAX(CASE WHEN re.is_user_mainline = 1 THEN 1 ELSE 0 END)::int AS is_user_mainline,
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
                  ON rl.line_id = lp.line_id
                LEFT JOIN repertoire_edges re
                  ON re.pos_id = lp.pos_id
                 AND re.uci_move = lp.uci_move
                 AND re.next_pos_id = lp.next_pos_id
                WHERE lp.pos_id = $1
                GROUP BY lp.uci_move, lp.next_pos_id
            ),
            pending_sidelines AS (
                SELECT sq.move_uci AS uci_move,
                       sq.move_uci AS san_move,
                       NULL::int AS next_pos_id,
                       0::int AS weight,
                       0::int AS is_priority_edge,
                       0::int AS is_user_mainline,
                       CASE WHEN $2 = 1 THEN 1 ELSE 0 END::int AS self_count,
                       1::int AS is_sideline_pending
                FROM sideline_queue sq
                WHERE sq.pos_id = $1
                  AND sq.status IN ('PENDING', 'EVAL_OK', 'EVAL_WARN')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM repertoire_rows rr
                      WHERE rr.uci_move = sq.move_uci
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
        )
    return [dict(row) for row in rows]


async def _fetch_tree_game_children_backend(
    pos_id: int,
    my_side_only: bool,
    request: Request | None,
) -> list[dict[str, Any]]:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.fetch_tree_game_children, pos_id, my_side_only=my_side_only)

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
              ON g.id = gp.game_id
            LEFT JOIN game_positions gp_next
              ON gp_next.game_id = gp.game_id
             AND gp_next.ply = gp.ply + 1
            WHERE {where_clause}
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


async def _fetch_review_propositions_backend(
    status_filter: str,
    request: Request | None,
) -> list[dict[str, Any]]:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.fetch_review_propositions, status_filter=status_filter)

    status_key = (status_filter or "pending").strip().lower()
    where = ["proposition_type = 'MISSING_COVERAGE_BRANCH'"]
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
            """
        )
    return [dict(row) for row in rows]


async def _fetch_review_proposition_detail_backend(
    proposition_id: int,
    request: Request | None,
) -> dict[str, Any] | None:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.fetch_review_proposition_detail, proposition_id)

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
            WHERE id = $1
            """,
            int(proposition_id),
        )
    if not row:
        return None
    data = dict(row)
    payload = data.get("detail_json")
    if payload:
        try:
            data["detail"] = json.loads(payload)
        except json.JSONDecodeError:
            data["detail"] = None
    else:
        data["detail"] = None
    return data


async def _fetch_branch_queue_backend(request: Request | None) -> list[dict[str, Any]]:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.fetch_branch_queue)

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
            ORDER BY bq.queued_at DESC, bq.proposition_id DESC
            """
        )
    return [dict(row) for row in rows]


async def _execute_review_action_backend(
    proposition_id: int,
    action: str,
    request: Request | None,
) -> dict[str, Any]:
    if SETTINGS.data_backend != "postgres":
        return await _with_sqlite(queries.execute_review_action, proposition_id, action)

    pid = int(proposition_id)
    action_key = (action or "").strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()

    req = _require_postgres_request(request)
    async with req.app.state.db_pool.acquire() as conn:
        async with conn.transaction():
            detail_row = await conn.fetchrow(
                """
                SELECT id, status, evidence_count, line_id_hint
                FROM review_propositions
                WHERE id = $1
                """,
                pid,
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
                WHERE bq.proposition_id = $1
                """,
                pid,
            )
            queue_before = dict(queue_before_row) if queue_before_row else None

            priority_before = None
            if line_id_hint:
                priority_before_row = await conn.fetchrow(
                    "SELECT priority_override FROM trainer_line_state WHERE line_id = $1",
                    str(line_id_hint),
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
                    WHERE id = $1
                      AND proposition_type = 'MISSING_COVERAGE_BRANCH'
                    """,
                    pid,
                    now_iso,
                )
                if tag.endswith('0'):
                    return {"success": False, "message": "Proposition not found."}
                await conn.execute(
                    """
                    INSERT INTO branch_queue (proposition_id, queue_status, queued_at)
                    VALUES ($1, 'QUEUED', $2)
                    ON CONFLICT (proposition_id) DO UPDATE
                    SET queue_status = EXCLUDED.queue_status,
                        queued_at = EXCLUDED.queued_at
                    """,
                    pid,
                    now_iso,
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
                    WHERE id = $1
                      AND proposition_type = 'MISSING_COVERAGE_BRANCH'
                    """,
                    pid,
                    int(detail_row["evidence_count"] or 0),
                    now_iso,
                )
                await conn.execute("DELETE FROM branch_queue WHERE proposition_id = $1", pid)
                message = "Proposition disapproved."
            elif action_key == "priority":
                if not line_id_hint:
                    return {"success": False, "message": "No line hint available to mark priority."}
                tag = await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET priority_override = 1
                    WHERE line_id = $1
                    """,
                    str(line_id_hint),
                )
                if tag.endswith('0'):
                    return {"success": False, "message": "Line not found in trainer state."}
                await conn.execute(
                    """
                    UPDATE review_propositions
                    SET updated_at = $2
                    WHERE id = $1
                    """,
                    pid,
                    now_iso,
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
                WHERE id = $1
                """,
                pid,
            )
            updated_detail = dict(updated_detail_row) if updated_detail_row else None
            if updated_detail is not None:
                payload = updated_detail.get("detail_json")
                if payload:
                    try:
                        updated_detail["detail"] = json.loads(payload)
                    except json.JSONDecodeError:
                        updated_detail["detail"] = None
                else:
                    updated_detail["detail"] = None

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
                WHERE bq.proposition_id = $1
                """,
                pid,
            )
            queue_after = dict(queue_after_row) if queue_after_row else None

            priority_after = None
            if line_id_hint:
                priority_after_row = await conn.fetchrow(
                    "SELECT priority_override FROM trainer_line_state WHERE line_id = $1",
                    str(line_id_hint),
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
        "priority_change": {
            "line_id": line_id_hint,
            "before": priority_before,
            "after": priority_after,
        },
    }

def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _load_runtime_config() -> RuntimeConfig:
    config = configparser.ConfigParser()
    if SETTINGS_INI_PATH.exists():
        config.read(SETTINGS_INI_PATH, encoding="utf-8")

    for section in ["PATHS", "ANALYSIS", "PLAYER", "FETCH"]:
        if section not in config:
            config[section] = {}

    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]
    fetch = config["FETCH"]

    player_name = (player.get("name") or "").strip()
    chesscom_usernames = _parse_list(fetch.get("chesscom_usernames"))
    lichess_usernames = _parse_list(fetch.get("lichess_usernames"))

    combined_names: list[str] = []
    seen: set[str] = set()
    for name in _parse_list(player_name) + chesscom_usernames + lichess_usernames:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        combined_names.append(name)

    return RuntimeConfig(
        repertoire_dir=paths.get("repertoire_dir", ""),
        games_dir=paths.get("games_dir", ""),
        database_path=paths.get("database_path", ""),
        stockfish_path=paths.get("stockfish_path", ""),
        piece_dir=paths.get("piece_dir", ""),
        engine_depth=_safe_int(analysis.get("engine_depth"), 20),
        max_plies=_safe_int(analysis.get("max_plies"), 30),
        player_name=player_name,
        player_names=combined_names,
        rating_band_size=_safe_int(player.get("rating_band_size"), 100),
        matching_mode=(analysis.get("matching_mode") or "STRICT").strip(),
        enable_engine_cache=_safe_int(analysis.get("enable_engine_cache"), 1) > 0,
        incremental_analysis=_safe_int(analysis.get("incremental_analysis"), 1) > 0,
        review_top_n=_safe_int(analysis.get("review_top_n"), 25),
        tabiya_top_n=_safe_int(analysis.get("tabiya_top_n"), 10),
        engine_workers=_safe_int(analysis.get("engine_workers"), 0),
        engine_worker_cap=_safe_int(analysis.get("engine_worker_cap"), 4),
        engine_threads=_safe_int(analysis.get("engine_threads"), 1),
        engine_hash_mb=_safe_int(analysis.get("engine_hash_mb"), 0),
        engine_mode=(analysis.get("engine_mode") or "adaptive").strip().lower(),
        engine_max_time_ms=_safe_int(analysis.get("engine_max_time_ms"), 300),
        engine_profile=(analysis.get("engine_profile") or "aggressive").strip().lower(),
        engine_cache_prune_non_active=_safe_int(analysis.get("engine_cache_prune_non_active"), 1) > 0,
        missing_coverage_proposal_threshold=_safe_int(analysis.get("missing_coverage_proposal_threshold"), 5),
        chesscom_usernames=chesscom_usernames,
        lichess_usernames=lichess_usernames,
        fetch_variants=_parse_list(fetch.get("variants") or fetch.get("fetch_variants") or "blitz,rapid,daily"),
        fetch_days_back=_safe_int(fetch.get("days_back") or fetch.get("fetch_days_back"), 180),
    )


def _runtime_settings_response(cfg: RuntimeConfig) -> RuntimeSettingsResponse:
    return RuntimeSettingsResponse(
        chesscom_usernames=cfg.chesscom_usernames,
        lichess_usernames=cfg.lichess_usernames,
        variants=cfg.fetch_variants,
        days_back=cfg.fetch_days_back,
        games_dir=cfg.games_dir,
        database_path=cfg.database_path,
        repertoire_dir=cfg.repertoire_dir,
        stockfish_path=cfg.stockfish_path,
        piece_dir=cfg.piece_dir,
        engine_depth=cfg.engine_depth,
        max_plies=cfg.max_plies,
        player_name=cfg.player_name,
        player_names=cfg.player_names,
        rating_band_size=cfg.rating_band_size,
        matching_mode=cfg.matching_mode,
        enable_engine_cache=cfg.enable_engine_cache,
        incremental_analysis=cfg.incremental_analysis,
        review_top_n=cfg.review_top_n,
        tabiya_top_n=cfg.tabiya_top_n,
        engine_workers=cfg.engine_workers,
        engine_worker_cap=cfg.engine_worker_cap,
        engine_threads=cfg.engine_threads,
        engine_hash_mb=cfg.engine_hash_mb,
        engine_mode=cfg.engine_mode,
        engine_max_time_ms=cfg.engine_max_time_ms,
        engine_profile=cfg.engine_profile,
        engine_cache_prune_non_active=cfg.engine_cache_prune_non_active,
        missing_coverage_proposal_threshold=cfg.missing_coverage_proposal_threshold,
    )


def _save_runtime_settings(payload: RuntimeSettingsUpdateRequest) -> RuntimeSettingsResponse:
    config = configparser.ConfigParser()
    if SETTINGS_INI_PATH.exists():
        config.read(SETTINGS_INI_PATH, encoding="utf-8")

    for section in ["PATHS", "ANALYSIS", "PLAYER", "FETCH"]:
        if section not in config:
            config[section] = {}

    fetch = config["FETCH"]
    normalized_chesscom = _normalize_list(payload.chesscom_usernames)
    normalized_lichess = _normalize_list(payload.lichess_usernames)
    normalized_variants = [variant.strip().lower() for variant in payload.variants if variant.strip()]
    normalized_variants = _normalize_list(normalized_variants)
    if not normalized_variants:
        raise api_error(status_code=422, error_code="VALIDATION_ERROR", detail="At least one variant is required")

    fetch["chesscom_usernames"] = ",".join(normalized_chesscom)
    fetch["lichess_usernames"] = ",".join(normalized_lichess)
    fetch["variants"] = ",".join(normalized_variants)
    fetch["days_back"] = str(payload.days_back)

    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]

    if payload.repertoire_dir is not None:
        paths["repertoire_dir"] = payload.repertoire_dir
    if payload.games_dir is not None:
        paths["games_dir"] = payload.games_dir
    if payload.database_path is not None:
        paths["database_path"] = payload.database_path
    if payload.stockfish_path is not None:
        paths["stockfish_path"] = payload.stockfish_path
    if payload.piece_dir is not None:
        paths["piece_dir"] = payload.piece_dir

    if payload.engine_depth is not None:
        analysis["engine_depth"] = str(payload.engine_depth)
    if payload.max_plies is not None:
        analysis["max_plies"] = str(payload.max_plies)
    if payload.matching_mode is not None:
        analysis["matching_mode"] = payload.matching_mode
    if payload.enable_engine_cache is not None:
        analysis["enable_engine_cache"] = "1" if payload.enable_engine_cache else "0"
    if payload.incremental_analysis is not None:
        analysis["incremental_analysis"] = "1" if payload.incremental_analysis else "0"
    if payload.review_top_n is not None:
        analysis["review_top_n"] = str(payload.review_top_n)
    if payload.tabiya_top_n is not None:
        analysis["tabiya_top_n"] = str(payload.tabiya_top_n)
    if payload.engine_workers is not None:
        analysis["engine_workers"] = str(payload.engine_workers)
    if payload.engine_worker_cap is not None:
        analysis["engine_worker_cap"] = str(payload.engine_worker_cap)
    if payload.engine_threads is not None:
        analysis["engine_threads"] = str(payload.engine_threads)
    if payload.engine_hash_mb is not None:
        analysis["engine_hash_mb"] = str(payload.engine_hash_mb)
    if payload.engine_mode is not None:
        analysis["engine_mode"] = payload.engine_mode
    if payload.engine_max_time_ms is not None:
        analysis["engine_max_time_ms"] = str(payload.engine_max_time_ms)
    if payload.engine_profile is not None:
        analysis["engine_profile"] = payload.engine_profile
    if payload.engine_cache_prune_non_active is not None:
        analysis["engine_cache_prune_non_active"] = "1" if payload.engine_cache_prune_non_active else "0"
    if payload.missing_coverage_proposal_threshold is not None:
        analysis["missing_coverage_proposal_threshold"] = str(payload.missing_coverage_proposal_threshold)

    if payload.player_name is not None:
        player["player_name"] = payload.player_name
    if payload.player_names is not None:
        player["player_names"] = ",".join(_normalize_list(payload.player_names))
    if payload.rating_band_size is not None:
        player["rating_band_size"] = str(payload.rating_band_size)

    with SETTINGS_INI_PATH.open("w", encoding="utf-8") as f:
        config.write(f)

    cfg = _load_runtime_config()
    return _runtime_settings_response(cfg)


class AnalysisRuntimeManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Literal["idle", "running", "completed", "failed"] = "idle"
        self._active_job_id: str | None = None
        self._active_run_type: str | None = None
        self._last_completed_job_id: str | None = None
        self._last_run_type: str | None = None
        self._last_error: str | None = None
        self._progress: dict[str, Any] | None = None
        self._progress_updated_at = datetime.now(timezone.utc)
        self._updated_at = datetime.now(timezone.utc)
        self._runs: list[AnalysisRunHistoryEntry] = []

    def _touch(self) -> None:
        self._updated_at = datetime.now(timezone.utc)

    def _set_progress(self, payload: dict[str, Any]) -> None:
        self._progress = payload
        self._progress_updated_at = datetime.now(timezone.utc)
        self._touch()

    def start_job(self, run_type: str, action: Callable[[Callable[[dict[str, Any]], None]], None]) -> str:
        with self._lock:
            if self._state == "running":
                raise RuntimeError("Analysis is already running.")
            job_id = str(uuid.uuid4())
            self._state = "running"
            self._active_job_id = job_id
            self._active_run_type = run_type
            self._last_error = None
            started_at = datetime.now(timezone.utc).isoformat()
            self._runs.insert(
                0,
                AnalysisRunHistoryEntry(
                    job_id=job_id,
                    run_type=run_type,
                    state="running",
                    started_at=started_at,
                ),
            )
            self._runs = self._runs[:50]
            self._set_progress({"message": f"Starting {run_type}", "done": 0, "total": 0})

        def worker() -> None:
            try:
                action(lambda payload: self._progress_callback(job_id, run_type, payload))
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._state = "failed"
                    self._last_error = str(exc)
                    self._last_run_type = run_type
                    self._last_completed_job_id = job_id
                    self._active_job_id = None
                    self._active_run_type = None
                    for idx, run in enumerate(self._runs):
                        if run.job_id == job_id:
                            self._runs[idx] = AnalysisRunHistoryEntry(
                                job_id=run.job_id,
                                run_type=run.run_type,
                                state="failed",
                                started_at=run.started_at,
                                finished_at=datetime.now(timezone.utc).isoformat(),
                                error=str(exc),
                            )
                            break
                    self._set_progress({"message": f"{run_type} failed", "error": str(exc)})
            else:
                with self._lock:
                    self._state = "completed"
                    self._last_run_type = run_type
                    self._last_completed_job_id = job_id
                    self._active_job_id = None
                    self._active_run_type = None
                    for idx, run in enumerate(self._runs):
                        if run.job_id == job_id:
                            self._runs[idx] = AnalysisRunHistoryEntry(
                                job_id=run.job_id,
                                run_type=run.run_type,
                                state="completed",
                                started_at=run.started_at,
                                finished_at=datetime.now(timezone.utc).isoformat(),
                                error=None,
                            )
                            break
                    self._set_progress({"message": f"{run_type} completed", "done": 1, "total": 1})

        thread = threading.Thread(target=worker, daemon=True, name=f"analysis-{run_type}")
        thread.start()
        return job_id

    def _progress_callback(self, job_id: str, run_type: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if self._active_job_id != job_id:
                return
            merged = {"job_id": job_id, "run_type": run_type, **payload}
            self._set_progress(merged)

    def status(self) -> AnalysisStatusResponse:
        with self._lock:
            return AnalysisStatusResponse(
                state=self._state,
                active_job_id=self._active_job_id,
                active_run_type=self._active_run_type,
                last_completed_job_id=self._last_completed_job_id,
                last_run_type=self._last_run_type,
                last_error=self._last_error,
                updated_at=self._updated_at.isoformat(),
            )

    def progress(self) -> AnalysisProgressResponse:
        with self._lock:
            return AnalysisProgressResponse(
                job_id=self._active_job_id,
                run_type=self._active_run_type,
                progress=self._progress,
                updated_at=self._progress_updated_at.isoformat(),
            )

    def runs(self, limit: int = 10) -> AnalysisRunHistoryResponse:
        with self._lock:
            bounded_limit = min(max(limit, 1), 50)
            return AnalysisRunHistoryResponse(runs=self._runs[:bounded_limit])


def _run_full_analysis(progress_cb) -> None:
    cfg = _load_runtime_config()
    conn = database.ensure_db(cfg.database_path, reset_on_mismatch=True)
    try:
        analysis_pipeline.run_analysis(conn, cfg, reset_db=False, progress_cb=progress_cb)
    finally:
        conn.close()


def _run_engine_only_analysis(progress_cb) -> None:
    cfg = _load_runtime_config()
    conn = database.ensure_db(cfg.database_path, reset_on_mismatch=True)
    try:
        analysis_pipeline.run_engine_analysis_only(conn, cfg, progress_cb=progress_cb)
    finally:
        conn.close()


def _run_smoke_test(progress_cb) -> None:
    cfg = _load_runtime_config()
    smoke_test_module.run_smoke_test(cfg, BASE_DIR, progress_cb=progress_cb)


def _run_fetch_games(progress_cb) -> None:
    cfg = _load_runtime_config()
    db_conn = database.ensure_db(cfg.database_path, reset_on_mismatch=True)
    try:
        existing_hashes = queries.fetch_existing_game_hashes(db_conn)
        progress_cb({"message": "Fetching remote games", "done": 0, "total": 1})
        summaries = game_fetcher.fetch_games(
            games_dir=Path(cfg.games_dir),
            chesscom_usernames=cfg.chesscom_usernames,
            lichess_usernames=cfg.lichess_usernames,
            variants=cfg.fetch_variants,
            days_back=cfg.fetch_days_back,
            state_path=Path(cfg.games_dir) / ".fetch_state.json",
            existing_pgn_hashes=existing_hashes,
        )
        progress_cb(
            {
                "message": "Fetch complete",
                "done": 1,
                "total": 1,
                "results": [summary.__dict__ for summary in summaries],
            }
        )
    finally:
        db_conn.close()

app = FastAPI(title="ChessGround API Service")
auth_scheme = HTTPBearer(auto_error=False)
REPERTOIRE_IMPORT_JOBS: dict[str, dict[str, Any]] = {}

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
    if SETTINGS.is_production_environment and SETTINGS.data_backend != "postgres":
        raise RuntimeError(
            "DATA_BACKEND must be 'postgres' in production environments. "
            "Set DATA_BACKEND=postgres."
        )

    if (
        SETTINGS.is_render_environment
        and SETTINGS.enforce_postgres_on_render
        and SETTINGS.data_backend != "postgres"
    ):
        raise RuntimeError(
            "DATA_BACKEND must be 'postgres' when running on Render. "
            "Set DATA_BACKEND=postgres."
        )

    app.state.db_pool = await db.create_pool()
    await db.ensure_schema(app.state.db_pool)
    app.state.redis = redis_client()
    await ensure_consumer_group(app.state.redis)
    app.state.analysis_runtime = AnalysisRuntimeManager()
    if SETTINGS.data_backend == "postgres":
        missing = await db.ensure_analysis_schema_exists(app.state.db_pool)
        if missing:
            async with app.state.db_pool.acquire() as conn:
                await db.apply_analysis_schema(conn)
            missing = await db.ensure_analysis_schema_exists(app.state.db_pool)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(
                "Postgres analysis schema is incomplete. "
                f"Missing table(s): {missing_csv}. "
                "Run `python -m backend.bootstrap_postgres_schema` before starting the API."
            )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await app.state.redis.close()
    await app.state.db_pool.close()


def to_response(record: asyncpg.Record) -> SidelineResponse:
    return SidelineResponse(
        id=str(record["id"]),
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


def _start_analysis_job(request: Request, run_type: str, action: Callable[[Callable[[dict[str, Any]], None]], None]) -> AnalysisRunResponse:
    runtime: AnalysisRuntimeManager = request.app.state.analysis_runtime
    try:
        job_id = runtime.start_job(run_type, action)
    except RuntimeError as exc:
        raise api_error(
            status_code=409,
            error_code="ANALYSIS_ALREADY_RUNNING",
            detail=str(exc),
        ) from exc
    return AnalysisRunResponse(accepted=True, detail="Job accepted", job_id=job_id, run_type=run_type)


@app.post('/analysis/run/full', response_model=AnalysisRunResponse, responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def run_full_analysis(request: Request, _: str = Depends(require_auth)) -> AnalysisRunResponse:
    return _start_analysis_job(request, "full-analysis", _run_full_analysis)


@app.post('/analysis/run/engine-only', response_model=AnalysisRunResponse, responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def run_engine_only_analysis(request: Request, _: str = Depends(require_auth)) -> AnalysisRunResponse:
    return _start_analysis_job(request, "engine-only-analysis", _run_engine_only_analysis)


@app.post('/analysis/run/fetch-games', response_model=AnalysisRunResponse, responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def run_fetch_games(request: Request, _: str = Depends(require_auth)) -> AnalysisRunResponse:
    return _start_analysis_job(request, "fetch-games", _run_fetch_games)


@app.post('/analysis/run/smoke-test', response_model=AnalysisRunResponse, responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def run_smoke_test(request: Request, _: str = Depends(require_auth)) -> AnalysisRunResponse:
    return _start_analysis_job(request, "smoke-test", _run_smoke_test)


@app.get('/analysis/status', response_model=AnalysisStatusResponse)
async def get_analysis_status(request: Request, _: str = Depends(require_auth)) -> AnalysisStatusResponse:
    runtime: AnalysisRuntimeManager = request.app.state.analysis_runtime
    return runtime.status()


@app.get('/analysis/progress', response_model=AnalysisProgressResponse)
async def get_analysis_progress(request: Request, _: str = Depends(require_auth)) -> AnalysisProgressResponse:
    runtime: AnalysisRuntimeManager = request.app.state.analysis_runtime
    return runtime.progress()


@app.get('/analysis/runs', response_model=AnalysisRunHistoryResponse)
async def get_analysis_runs(request: Request, limit: int = 10, _: str = Depends(require_auth)) -> AnalysisRunHistoryResponse:
    runtime: AnalysisRuntimeManager = request.app.state.analysis_runtime
    return runtime.runs(limit=limit)


@app.get('/auth/validate', response_model=AuthValidateResponse, responses={401: {"model": ErrorResponse}})
async def auth_validate(_: str = Depends(require_auth)) -> AuthValidateResponse:
    return AuthValidateResponse(ok=True, detail="Token is valid")


@app.get('/settings/runtime', response_model=RuntimeSettingsResponse, responses={401: {"model": ErrorResponse}})
async def get_runtime_settings(_: str = Depends(require_auth)) -> RuntimeSettingsResponse:
    cfg = _load_runtime_config()
    return _runtime_settings_response(cfg)


@app.put('/settings/runtime', response_model=RuntimeSettingsResponse, responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
async def update_runtime_settings(payload: RuntimeSettingsUpdateRequest, _: str = Depends(require_auth)) -> RuntimeSettingsResponse:
    return _save_runtime_settings(payload)


@app.post('/repertoires/import', response_model=RepertoireImportResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def import_repertoires(file: UploadFile = File(...), _: str = Depends(require_auth)) -> RepertoireImportResponse:
    cfg = _load_runtime_config()
    if not cfg.database_path:
        raise api_error(400, "INVALID_RUNTIME_CONFIG", "Database path is missing in runtime settings.")

    payload = await file.read()
    if not payload:
        raise api_error(400, "EMPTY_UPLOAD", "Uploaded file is empty.")

    upload_hash = hashlib.sha256(payload).hexdigest()

    duplicate_job = next((job for job in REPERTOIRE_IMPORT_JOBS.values() if job.get("upload_hash") == upload_hash), None)
    if duplicate_job:
        raise api_error(
            409,
            "UPLOAD_ALREADY_IMPORTED",
            "This exact upload payload was already imported. Please upload a new export.",
        )

    try:
        parsed_lines = repertoire_import.parse_repertoire_upload(payload, file.filename or "upload")
    except ValueError as exc:
        raise api_error(400, "INVALID_UPLOAD", str(exc)) from exc

    conn = database.ensure_db(cfg.database_path, reset_on_mismatch=True)
    try:
        inserted, duplicates, total = repertoire_import.ingest_repertoire_lines(conn, parsed_lines)
    finally:
        conn.close()

    job_id = str(uuid.uuid4())
    progress = {
        "message": "Import completed",
        "done": total,
        "total": total,
        "inserted_lines": inserted,
        "duplicate_lines": duplicates,
    }
    REPERTOIRE_IMPORT_JOBS[job_id] = {
        "id": job_id,
        "status": "completed",
        "upload_hash": upload_hash,
        "progress": progress,
    }

    detail = (
        f"Imported {inserted} repertoire lines."
        if duplicates == 0
        else f"Imported {inserted} repertoire lines; skipped {duplicates} duplicate line(s)."
    )
    return RepertoireImportResponse(
        job_id=job_id,
        status="completed",
        upload_hash=upload_hash,
        inserted_lines=inserted,
        duplicate_lines=duplicates,
        total_lines=total,
        detail=detail,
    )


@app.get('/repertoires/import-jobs/{job_id}', response_model=RepertoireImportJobResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def get_repertoire_import_job(job_id: str, _: str = Depends(require_auth)) -> RepertoireImportJobResponse:
    job = REPERTOIRE_IMPORT_JOBS.get(job_id)
    if not job:
        raise api_error(404, "IMPORT_JOB_NOT_FOUND", "Repertoire import job was not found.")
    return RepertoireImportJobResponse(id=job["id"], status=job["status"], progress=job["progress"])


@app.post(
    "/sidelines",
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
        row = await db.insert_sideline_request(
            conn,
            request_id=request_id,
            game_id=payload.game_id,
            move_ply=payload.move_ply,
            requested_by=principal,
            idempotency_key=idempotency_key,
            payload=serialized_payload,
        )

        if row is None:
            existing = await db.fetch_by_idempotency_key(conn, idempotency_key)
            if existing is None:
                raise api_error(
                    status_code=500,
                    error_code="IDEMPOTENCY_CONFLICT_RESOLUTION_FAILED",
                    detail="Idempotency key existed but record lookup failed",
                )
            return to_response(existing)

    await enqueue_job(
        request.app.state.redis,
        {
            "job_id": request_id,
            "idempotency_key": idempotency_key,
            "attempt": "0",
        },
    )

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
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    _: str = Depends(require_auth),
) -> list[GameOverviewResponse]:
    bounded_limit = min(max(limit, 1), 200)
    bounded_offset = max(offset, 0)
    normalized_sort_by = sort_by if sort_by in {"date", "result", "compliance", "id"} else "date"
    normalized_sort_dir = sort_dir if sort_dir in {"asc", "desc"} else "desc"
    rows = await fetch_games(
        limit=bounded_limit,
        offset=bounded_offset,
        result=result,
        compliance=compliance,
        line_id=line_id,
        player=player,
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


@app.get("/overview/summary", response_model=dict[str, Any])
async def get_overview_summary(_: str = Depends(require_auth)) -> dict[str, Any]:
    return await fetch_overview_summary()


@app.get("/lines/stats", response_model=list[dict[str, Any]])
async def get_lines_stats(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_lines_stats()


@app.get("/time-usage/stats", response_model=list[dict[str, Any]])
async def get_time_usage_stats(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_time_usage_stats()


@app.get("/rating-bands/stats", response_model=list[dict[str, Any]])
async def get_rating_band_stats(band_size: int = 100, _: str = Depends(require_auth)) -> list[dict[str, Any]]:
    bounded_band_size = min(max(band_size, 50), 400)
    return await fetch_rating_band_stats(bounded_band_size)


@app.get("/insights", response_model=list[dict[str, Any]])
async def list_insights(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_insights()


@app.get("/review/items", response_model=list[dict[str, Any]])
async def list_review_items(_: str = Depends(require_auth)) -> list[dict[str, Any]]:
    return await fetch_review_items()


@app.get("/lines/tree/browse", response_model=TreeBrowseResponse)
async def get_lines_tree_browse(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeBrowseResponse:
    repertoire_rows = await _fetch_tree_repertoire_children_backend(pos_id, my_side_only, request)
    game_rows = await _fetch_tree_game_children_backend(pos_id, my_side_only, request)
    return TreeBrowseResponse(
        pos_id=pos_id,
        my_side_only=my_side_only,
        repertoire_children=[TreeBrowseMoveResponse(**row) for row in repertoire_rows],
        game_children=game_rows,
    )


@app.get("/lines/tree/coverage", response_model=TreeCoverageResponse)
async def get_lines_tree_coverage(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeCoverageResponse:
    repertoire_rows = await _fetch_tree_repertoire_children_backend(pos_id, my_side_only, request)
    game_rows = await _fetch_tree_game_children_backend(pos_id, my_side_only, request)
    rep_moves = {str(row.get("uci_move") or "") for row in repertoire_rows if row.get("uci_move")}
    game_moves = {str(row.get("uci_move") or "") for row in game_rows if row.get("uci_move")}
    covered = len(rep_moves & game_moves)
    total = len(rep_moves)
    coverage_pct = (covered / total * 100.0) if total else 0.0
    return TreeCoverageResponse(
        pos_id=pos_id,
        total_repertoire_moves=total,
        covered_by_games=covered,
        coverage_pct=coverage_pct,
    )


@app.get("/lines/tree/branch-metrics", response_model=TreeBranchMetricsResponse)
async def get_lines_tree_branch_metrics(
    pos_id: int = 1,
    my_side_only: bool = True,
    request: Request = None,
    _: str = Depends(require_auth),
) -> TreeBranchMetricsResponse:
    repertoire_rows = await _fetch_tree_repertoire_children_backend(pos_id, my_side_only, request)
    game_rows = await _fetch_tree_game_children_backend(pos_id, my_side_only, request)
    repertoire_sorted = sorted(repertoire_rows, key=lambda row: int(row.get("weight") or 0), reverse=True)
    game_sorted = sorted(game_rows, key=lambda row: int(row.get("games") or 0), reverse=True)
    return TreeBranchMetricsResponse(
        pos_id=pos_id,
        top_repertoire_branches=repertoire_sorted[:10],
        top_game_branches=game_sorted[:10],
    )


def _require_postgres_trainer_sessions() -> None:
    if SETTINGS.data_backend != "postgres":
        raise api_error(
            status_code=501,
            error_code="NOT_IMPLEMENTED",
            detail="Trainer sessions API is implemented only for PostgreSQL backend.",
        )


def _trainer_player_moves_for_side(line_moves: list[dict[str, Any]], side_to_play: str) -> list[dict[str, Any]]:
    player_is_white = (side_to_play or "white").lower() != "black"
    return [
        move
        for move in line_moves
        if (int(move.get("ply") or 0) % 2 == 1) == player_is_white
    ]


async def _ensure_trainer_state_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO trainer_line_state (line_id, side_to_play)
        SELECT line_id, COALESCE(side_to_play, 'white')
        FROM repertoire_lines
        ON CONFLICT (line_id) DO NOTHING
        """
    )
    await conn.execute(
        """
        UPDATE trainer_line_state tls
        SET side_to_play = COALESCE(rl.side_to_play, 'white')
        FROM repertoire_lines rl
        WHERE rl.line_id = tls.line_id
        """
    )


async def _fetch_trainer_line_info_postgres(conn: asyncpg.Connection, line_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT rl.line_id, rl.side_to_play, rl.is_priority,
               tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
               tls.auto_priority_score, tls.focus_max_ply
        FROM repertoire_lines rl
        JOIN trainer_line_state tls ON rl.line_id = tls.line_id
        WHERE rl.line_id = $1
        """,
        line_id,
    )
    return dict(row) if row else None


async def _fetch_line_moves_postgres(conn: asyncpg.Connection, line_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT ply, san_move, uci_move, pos_id, next_pos_id
        FROM line_positions
        WHERE line_id = $1
        ORDER BY ply
        """,
        line_id,
    )
    return [dict(row) for row in rows]


async def _trainer_session_snapshot_postgres(conn: asyncpg.Connection, session: dict[str, Any]) -> TrainerSessionResponse:
    line_info = await _fetch_trainer_line_info_postgres(conn, str(session["line_id"]))
    if not line_info:
        raise ValueError("Line not found in trainer state")

    line_moves = await _fetch_line_moves_postgres(conn, str(session["line_id"]))
    player_moves = _trainer_player_moves_for_side(line_moves, str(line_info.get("side_to_play") or "white"))
    player_idx = int(session.get("player_move_index") or 0)
    completed = bool(session.get("completed")) or player_idx >= len(player_moves)
    expected = None if completed else str(player_moves[player_idx].get("uci_move") or "")

    phase: Literal["prompt", "user_attempt", "reveal_explanation", "grading", "next_item_transition", "completed"]
    if completed:
        phase = "completed"
    else:
        phase = "prompt" if player_idx == 0 else "user_attempt"

    return TrainerSessionResponse(
        session_id=str(session["id"]),
        line_id=str(session["line_id"]),
        mode=session["mode"],
        player_move_index=player_idx,
        expected_move_uci=expected or None,
        completed=completed,
        next_step=TrainerSessionNextStep(
            phase=phase,
            expected_move_uci=expected or None,
            explanation="Play the expected repertoire move.",
        ),
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
                WHERE tls.learned = $1
                ORDER BY rl.line_id
                LIMIT 1
                """,
                1 if payload.mode == "review" else 0,
            )
            if not row:
                raise api_error(404, "NOT_FOUND", "No trainer lines available for mode")
            line_id = str(row["line_id"])

        line_info = await _fetch_trainer_line_info_postgres(conn, line_id)
        if not line_info:
            raise api_error(404, "NOT_FOUND", "Line not found in trainer state")

        session_id = str(uuid.uuid4())
        session_row = await conn.fetchrow(
            """
            INSERT INTO trainer_sessions (id, line_id, mode, player_move_index, had_incorrect, completed)
            VALUES ($1::uuid, $2, $3, 0, 0, 0)
            RETURNING id, line_id, mode, player_move_index, had_incorrect, completed
            """,
            session_id,
            line_id,
            payload.mode,
        )
        if not session_row:
            raise api_error(500, "INTERNAL_ERROR", "Failed to create trainer session")
        return await _trainer_session_snapshot_postgres(conn, dict(session_row))


@app.post("/trainer/sessions/{session_id}/answer", response_model=TrainerSessionAnswerResponse)
async def answer_trainer_session(session_id: str, payload: TrainerSessionAnswerRequest, request: Request, _: str = Depends(require_auth)) -> TrainerSessionAnswerResponse:
    _require_postgres_trainer_sessions()

    async with request.app.state.db_pool.acquire() as conn:
        await _ensure_trainer_state_postgres(conn)
        session = await conn.fetchrow(
            """
            SELECT id, line_id, mode, player_move_index, had_incorrect, completed
            FROM trainer_sessions
            WHERE id = $1::uuid
            """,
            session_id,
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
        is_correct = payload.answer_uci == expected_move
        had_incorrect = int(session_data.get("had_incorrect") or 0)

        if is_correct:
            player_idx += 1
            completed = 1 if player_idx >= len(player_moves) else 0
        else:
            had_incorrect = 1
            completed = 0

        await conn.execute(
            """
            UPDATE trainer_sessions
            SET player_move_index = $2,
                had_incorrect = $3,
                completed = $4,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            session_id,
            player_idx,
            had_incorrect,
            completed,
        )

        if completed:
            current_streak = int(line_info.get("correct_streak") or 0)
            if had_incorrect:
                await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET learned = 1,
                        needs_review = 1,
                        correct_streak = 0,
                        times_incorrect = times_incorrect + 1,
                        last_seen = $2
                    WHERE line_id = $1
                    """,
                    str(session_data["line_id"]),
                    datetime.now(timezone.utc).isoformat(),
                )
            else:
                await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET learned = 1,
                        needs_review = 0,
                        correct_streak = $2,
                        times_correct = times_correct + 1,
                        last_seen = $3
                    WHERE line_id = $1
                    """,
                    str(session_data["line_id"]),
                    current_streak + 1,
                    datetime.now(timezone.utc).isoformat(),
                )

        state_row = await conn.fetchrow(
            """
            SELECT line_id, learned, needs_review, correct_streak, times_correct, times_incorrect
            FROM trainer_line_state
            WHERE line_id = $1
            """,
            str(session_data["line_id"]),
        )
        if not state_row:
            raise api_error(404, "NOT_FOUND", "Line not found after trainer session answer")

        next_expected = None
        next_phase: Literal["prompt", "user_attempt", "reveal_explanation", "grading", "next_item_transition", "completed"] = "completed"
        explanation: str | None = None
        feedback = "Correct." if is_correct else "Incorrect. Review the expected move and try again."

        if not completed:
            next_expected = expected_move if not is_correct else str(player_moves[player_idx].get("uci_move") or "")
            next_phase = "reveal_explanation" if not is_correct else "user_attempt"
            explanation = "Expected move shown for remediation." if not is_correct else "Continue to the next player move."
        else:
            next_phase = "next_item_transition"
            explanation = "Line complete. Move to the next queue item."

        return TrainerSessionAnswerResponse(
            session_id=session_id,
            line_id=str(session_data["line_id"]),
            mode=session_data["mode"],
            answer_uci=payload.answer_uci,
            expected_move_uci=expected_move,
            is_correct=is_correct,
            feedback=feedback,
            learned=int(state_row["learned"]),
            needs_review=int(state_row["needs_review"]),
            correct_streak=int(state_row["correct_streak"]),
            times_correct=int(state_row["times_correct"]),
            times_incorrect=int(state_row["times_incorrect"]),
            completed=bool(completed),
            next_step=TrainerSessionNextStep(
                phase=next_phase,
                expected_move_uci=next_expected,
                explanation=explanation,
            ),
        )


@app.get("/trainer/queue", response_model=TrainerQueueResponse)
async def get_trainer_queue(
    request: Request,
    mode: Literal["learn", "review"] = "review",
    _: str = Depends(require_auth),
) -> TrainerQueueResponse:
    learned_only = mode == "review"

    if SETTINGS.data_backend == "postgres":
        async with request.app.state.db_pool.acquire() as conn:
            await _ensure_trainer_state_postgres(conn)
            rows = await conn.fetch(
                """
                SELECT rl.line_id, rl.is_priority, rl.side_to_play,
                       tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
                       tls.auto_priority_score, tls.focus_max_ply
                FROM repertoire_lines rl
                JOIN trainer_line_state tls ON rl.line_id = tls.line_id
                WHERE tls.learned = $1
                """,
                1 if learned_only else 0,
            )
        return TrainerQueueResponse(mode=mode, items=[TrainerQueueEntry(**dict(row)) for row in rows])

    def _fetch(conn: sqlite3.Connection):
        queries.ensure_trainer_state(conn)
        return queries.fetch_trainer_candidates(conn, learned_only)

    rows = await _with_sqlite(_fetch)
    return TrainerQueueResponse(mode=mode, items=[TrainerQueueEntry(**row) for row in rows])


@app.post("/trainer/outcomes", response_model=TrainerOutcomeResponse)
async def post_trainer_outcome(
    payload: TrainerOutcomeRequest,
    request: Request,
    _: str = Depends(require_auth),
) -> TrainerOutcomeResponse:
    if SETTINGS.data_backend == "postgres":
        async with request.app.state.db_pool.acquire() as conn:
            await _ensure_trainer_state_postgres(conn)
            info = await _fetch_trainer_line_info_postgres(conn, payload.line_id)
            if not info:
                raise api_error(404, "NOT_FOUND", "Line not found in trainer state")

            current_streak = int(info.get("correct_streak") or 0)
            now_iso = datetime.now(timezone.utc).isoformat()
            if payload.is_correct:
                await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET learned = COALESCE($2, learned),
                        needs_review = 0,
                        correct_streak = $3,
                        times_correct = times_correct + 1,
                        last_seen = $4
                    WHERE line_id = $1
                    """,
                    payload.line_id,
                    1 if payload.mode == "learn" else None,
                    current_streak + 1,
                    now_iso,
                )
            else:
                await conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET needs_review = 1,
                        correct_streak = 0,
                        times_incorrect = times_incorrect + 1,
                        last_seen = $2
                    WHERE line_id = $1
                    """,
                    payload.line_id,
                    now_iso,
                )

            row = await conn.fetchrow(
                """
                SELECT line_id, learned, needs_review, correct_streak, times_correct, times_incorrect
                FROM trainer_line_state
                WHERE line_id = $1
                """,
                payload.line_id,
            )
            if not row:
                raise api_error(404, "NOT_FOUND", "Line not found after update")
            return TrainerOutcomeResponse(**dict(row))

    def _update(conn: sqlite3.Connection):
        info = queries.fetch_trainer_line_info(conn, payload.line_id)
        if not info:
            raise ValueError("Line not found in trainer state")

        current_streak = int(info.get("correct_streak") or 0)
        if payload.is_correct:
            queries.update_trainer_state(
                conn,
                payload.line_id,
                learned=1 if payload.mode == "learn" else None,
                needs_review=0,
                correct_streak=current_streak + 1,
                times_correct_delta=1,
                last_seen=datetime.now(timezone.utc).isoformat(),
            )
        else:
            queries.update_trainer_state(
                conn,
                payload.line_id,
                needs_review=1,
                correct_streak=0,
                times_incorrect_delta=1,
                last_seen=datetime.now(timezone.utc).isoformat(),
            )

        row = conn.execute(
            """
            SELECT line_id, learned, needs_review, correct_streak, times_correct, times_incorrect
            FROM trainer_line_state
            WHERE line_id = ?
            """,
            (payload.line_id,),
        ).fetchone()
        if not row:
            raise ValueError("Line not found after update")
        return dict(row)

    try:
        result = await _with_sqlite(_update)
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
    return TrainerOutcomeResponse(**result)


@app.post("/trainer/priority-override", response_model=TrainerQueueEntry)
async def set_trainer_priority_override(
    payload: TrainerPriorityOverrideRequest,
    request: Request,
    _: str = Depends(require_auth),
) -> TrainerQueueEntry:
    if SETTINGS.data_backend == "postgres":
        async with request.app.state.db_pool.acquire() as conn:
            await _ensure_trainer_state_postgres(conn)
            await conn.execute(
                """
                UPDATE trainer_line_state
                SET priority_override = $2
                WHERE line_id = $1
                """,
                payload.line_id,
                int(payload.value),
            )
            row = await _fetch_trainer_line_info_postgres(conn, payload.line_id)
            if not row:
                raise api_error(404, "NOT_FOUND", "Line not found in trainer state")
            return TrainerQueueEntry(**row)

    def _set(conn: sqlite3.Connection):
        queries.set_trainer_priority_override(conn, payload.line_id, payload.value)
        row = queries.fetch_trainer_line_info(conn, payload.line_id)
        if not row:
            raise ValueError("Line not found in trainer state")
        return row

    try:
        updated = await _with_sqlite(_set)
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
    return TrainerQueueEntry(**updated)


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
        priority_change=ReviewPriorityDelta(**result["priority_change"]) if result.get("priority_change") else None,
    )
