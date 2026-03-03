from __future__ import annotations

import uuid
import threading
import configparser
import asyncio
import sqlite3
from datetime import datetime
from datetime import timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Literal

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend import db
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


class ReviewActionRequest(BaseModel):
    proposition_id: int = Field(ge=1)
    action: Literal["done", "defer", "priority"]


class ReviewActionResponse(BaseModel):
    success: bool
    message: str


class AuthValidateResponse(BaseModel):
    ok: bool
    detail: str




def _sqlite_runtime_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SETTINGS.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


async def _with_sqlite(fn, *args, **kwargs):
    if SETTINGS.data_backend == "postgres":
        raise RuntimeError(
            "This endpoint is currently implemented for SQLite data backend. "
            "Use DATA_BACKEND=sqlite locally until Postgres parity endpoints are added."
        )

    def runner():
        with _sqlite_runtime_conn() as conn:
            return fn(conn, *args, **kwargs)

    return await asyncio.to_thread(runner)

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
        fetch_variants=_parse_list(fetch.get("variants") or "blitz,rapid,daily"),
        fetch_days_back=_safe_int(fetch.get("days_back"), 180),
    )


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
                    self._set_progress({"message": f"{run_type} failed", "error": str(exc)})
            else:
                with self._lock:
                    self._state = "completed"
                    self._last_run_type = run_type
                    self._last_completed_job_id = job_id
                    self._active_job_id = None
                    self._active_run_type = None
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


@app.get('/auth/validate', response_model=AuthValidateResponse, responses={401: {"model": ErrorResponse}})
async def auth_validate(_: str = Depends(require_auth)) -> AuthValidateResponse:
    return AuthValidateResponse(ok=True, detail="Token is valid")


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
    _: str = Depends(require_auth),
) -> list[GameOverviewResponse]:
    bounded_limit = min(max(limit, 1), 200)
    bounded_offset = max(offset, 0)
    rows = await fetch_games(limit=bounded_limit, offset=bounded_offset)
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
async def get_lines_tree_browse(pos_id: int = 1, my_side_only: bool = True, _: str = Depends(require_auth)) -> TreeBrowseResponse:
    repertoire_rows = await _with_sqlite(queries.fetch_tree_repertoire_children, pos_id, my_side_only=my_side_only)
    game_rows = await _with_sqlite(queries.fetch_tree_game_children, pos_id, my_side_only=my_side_only)
    return TreeBrowseResponse(
        pos_id=pos_id,
        my_side_only=my_side_only,
        repertoire_children=[TreeBrowseMoveResponse(**row) for row in repertoire_rows],
        game_children=game_rows,
    )


@app.get("/lines/tree/coverage", response_model=TreeCoverageResponse)
async def get_lines_tree_coverage(pos_id: int = 1, my_side_only: bool = True, _: str = Depends(require_auth)) -> TreeCoverageResponse:
    repertoire_rows = await _with_sqlite(queries.fetch_tree_repertoire_children, pos_id, my_side_only=my_side_only)
    game_rows = await _with_sqlite(queries.fetch_tree_game_children, pos_id, my_side_only=my_side_only)
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
async def get_lines_tree_branch_metrics(pos_id: int = 1, my_side_only: bool = True, _: str = Depends(require_auth)) -> TreeBranchMetricsResponse:
    repertoire_rows = await _with_sqlite(queries.fetch_tree_repertoire_children, pos_id, my_side_only=my_side_only)
    game_rows = await _with_sqlite(queries.fetch_tree_game_children, pos_id, my_side_only=my_side_only)
    repertoire_sorted = sorted(repertoire_rows, key=lambda row: int(row.get("weight") or 0), reverse=True)
    game_sorted = sorted(game_rows, key=lambda row: int(row.get("games") or 0), reverse=True)
    return TreeBranchMetricsResponse(
        pos_id=pos_id,
        top_repertoire_branches=repertoire_sorted[:10],
        top_game_branches=game_sorted[:10],
    )


@app.get("/trainer/queue", response_model=TrainerQueueResponse)
async def get_trainer_queue(mode: Literal["learn", "review"] = "review", _: str = Depends(require_auth)) -> TrainerQueueResponse:
    learned_only = mode == "review"

    def _fetch(conn: sqlite3.Connection):
        queries.ensure_trainer_state(conn)
        return queries.fetch_trainer_candidates(conn, learned_only)

    rows = await _with_sqlite(_fetch)
    return TrainerQueueResponse(mode=mode, items=[TrainerQueueEntry(**row) for row in rows])


@app.post("/trainer/outcomes", response_model=TrainerOutcomeResponse)
async def post_trainer_outcome(payload: TrainerOutcomeRequest, _: str = Depends(require_auth)) -> TrainerOutcomeResponse:
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
async def set_trainer_priority_override(payload: TrainerPriorityOverrideRequest, _: str = Depends(require_auth)) -> TrainerQueueEntry:
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
async def list_review_actions(status: Literal["pending", "approved", "disapproved", "all"] = "pending", _: str = Depends(require_auth)) -> list[ReviewPropositionResponse]:
    rows = await _with_sqlite(queries.fetch_review_propositions, status_filter=status)
    return [ReviewPropositionResponse(**row) for row in rows]


@app.post("/review/actions", response_model=ReviewActionResponse)
async def execute_review_action(payload: ReviewActionRequest, _: str = Depends(require_auth)) -> ReviewActionResponse:
    if payload.action == "done":
        success, message = await _with_sqlite(queries.approve_review_proposition, payload.proposition_id)
    elif payload.action == "defer":
        success, message = await _with_sqlite(queries.disapprove_review_proposition, payload.proposition_id)
    else:
        def _mark_priority(conn: sqlite3.Connection):
            detail = queries.fetch_review_proposition_detail(conn, payload.proposition_id)
            if not detail:
                return False, "Proposition not found."
            line_id = detail.get("line_id_hint")
            if not line_id:
                return False, "No line hint available to mark priority."
            queries.set_trainer_priority_override(conn, str(line_id), 1)
            return True, f"Priority override enabled for {line_id}."

        success, message = await _with_sqlite(_mark_priority)

    if not success:
        raise api_error(404, "NOT_FOUND", message)
    return ReviewActionResponse(success=success, message=message)
