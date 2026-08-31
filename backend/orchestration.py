from __future__ import annotations

import json
from typing import Any

import asyncpg

from analysis.compliance import classify_compliance_with_completion, who_left_first
from analysis.matching import find_best_match
from backend import jobs
from backend.queue import enqueue_job
from backend.settings import SETTINGS


ANALYSIS_JOB_TYPES = {
    "full-analysis",
    "incremental-analysis",
    "engine-only-analysis",
    "line-matching-reanalysis",
    "game-details-reanalysis",
    "per-game-reanalysis",
    "review-insight-regeneration",
    "smoke-analysis",
}


async def _schedule_engine_positions(
    conn: asyncpg.Connection,
    redis,
    step: dict[str, Any],
    game_id: int | None,
    artifact_ids: list[str] | None = None,
    game_ids: list[int] | None = None,
    depth: int = SETTINGS.stockfish_depth,
    max_plies: int = 30,
    engine_id: str = SETTINGS.stockfish_engine_id,
) -> int:
    rows = await conn.fetch(
        """
        SELECT DISTINCT p.id AS pos_id, p.fen_norm
        FROM game_positions gp
        CROSS JOIN LATERAL (VALUES (gp.pos_id), (gp.next_pos_id)) AS required(pos_id)
        JOIN positions p ON p.id = required.pos_id
        LEFT JOIN engine_cache cache
          ON cache.pos_id = p.id AND cache.depth = $2 AND cache.engine_id = $5
         AND cache.mode = 'fixed' AND cache.max_time_ms=0 AND cache.options_hash = ''
        WHERE gp.workspace_id = $1::uuid
          AND ($3::bigint IS NULL OR gp.game_id = $3)
          AND ($4::uuid[] IS NULL OR EXISTS (
              SELECT 1 FROM games game
              WHERE game.workspace_id=gp.workspace_id AND game.id=gp.game_id
                AND game.source_artifact_id=ANY($4::uuid[])
          ))
          AND ($6::bigint[] IS NULL OR gp.game_id=ANY($6::bigint[]))
          AND gp.ply <= $7
          AND cache.pos_id IS NULL
        ORDER BY p.id
        """,
        step["workspace_id"],
        depth,
        game_id,
        artifact_ids,
        engine_id,
        game_ids,
        max_plies,
    )
    scheduled = 0
    for row in rows:
        payload = {
            "fen": str(row["fen_norm"]),
            "pos_id": int(row["pos_id"]),
            "depth": depth,
            "engine_id": engine_id,
            "mode": "fixed",
            "max_time_ms": 0,
            "options_hash": "",
        }
        child, created = await jobs.add_step(
            conn,
            job_id=step["job_id"],
            workspace_id=step["workspace_id"],
            workload_class="engine",
            step_type="engine-position",
            payload=payload,
            deduplication_key=(
                f"engine:{row['pos_id']}:{engine_id}:{depth}:fixed:0:"
            ),
        )
        if created:
            await enqueue_job(redis, "engine", jobs.redis_message(child, "engine-position"))
            scheduled += 1
    return scheduled


async def _match_games(
    conn: asyncpg.Connection,
    step: dict[str, Any],
    game_id: int | None,
    artifact_ids: list[str] | None = None,
    game_ids: list[int] | None = None,
    matching_mode: str = "STRICT",
) -> int:
    line_rows = await conn.fetch(
        """
        SELECT line.line_id, compact.moves_json, compact.pos_ids_json, compact.ply_count
        FROM repertoire_lines line
        JOIN repertoire_compact compact
          ON compact.workspace_id = line.workspace_id AND compact.line_id = line.line_id
        WHERE line.workspace_id = $1::uuid
        """,
        step["workspace_id"],
    )
    lines: list[dict[str, Any]] = []
    lengths: dict[str, int] = {}
    for row in line_rows:
        moves = row["moves_json"]
        pos_ids = row["pos_ids_json"]
        if isinstance(moves, str):
            moves = json.loads(moves)
        if isinstance(pos_ids, str):
            pos_ids = json.loads(pos_ids)
        line_id = str(row["line_id"])
        lines.append({
            "line_id": line_id,
            "moves_uci": list(moves or []),
            "pos_ids": [int(value) for value in (pos_ids or [])],
        })
        lengths[line_id] = int(row["ply_count"])

    game_rows = await conn.fetch(
        """
        SELECT game.id, game.player_color,
               COALESCE(jsonb_agg(gp.uci_move ORDER BY gp.ply) FILTER (WHERE gp.uci_move IS NOT NULL), '[]') AS moves,
               COALESCE(jsonb_agg(gp.pos_id ORDER BY gp.ply) FILTER (WHERE gp.pos_id IS NOT NULL), '[]') AS pos_ids
        FROM games game
        LEFT JOIN game_positions gp
          ON gp.workspace_id = game.workspace_id AND gp.game_id = game.id
        WHERE game.workspace_id = $1::uuid AND ($2::bigint IS NULL OR game.id = $2)
          AND ($3::uuid[] IS NULL OR game.source_artifact_id=ANY($3::uuid[]))
          AND ($4::bigint[] IS NULL OR game.id=ANY($4::bigint[]))
        GROUP BY game.id, game.player_color
        """,
        step["workspace_id"],
        game_id,
        artifact_ids,
        game_ids,
    )
    matched = 0
    for row in game_rows:
        moves = row["moves"]
        pos_ids = row["pos_ids"]
        if isinstance(moves, str):
            moves = json.loads(moves)
        if isinstance(pos_ids, str):
            pos_ids = json.loads(pos_ids)
        result = find_best_match(
            list(moves or []),
            [int(value) for value in (pos_ids or [])],
            lines,
            str(row["player_color"] or "white"),
            matching_mode,
        )
        line_len = lengths.get(result.matched_line_id or "", 0)
        compliance = classify_compliance_with_completion(
            result.deviation_ply_opp,
            result.deviation_ply_self,
            result.max_matched_ply,
            line_len,
        )
        await conn.execute(
            """
            INSERT INTO matches(
                workspace_id, game_id, analysis_run_id, matched_line_id, matching_mode,
                max_matched_ply, deviation_ply_you, deviation_ply_opp, compliance,
                who_left_first, tie_lines_json
            ) VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
            ON CONFLICT (workspace_id, analysis_run_id, game_id) DO UPDATE SET
                matched_line_id = EXCLUDED.matched_line_id,
                matching_mode = EXCLUDED.matching_mode,
                max_matched_ply = EXCLUDED.max_matched_ply,
                deviation_ply_you = EXCLUDED.deviation_ply_you,
                deviation_ply_opp = EXCLUDED.deviation_ply_opp,
                compliance = EXCLUDED.compliance,
                who_left_first = EXCLUDED.who_left_first,
                tie_lines_json = EXCLUDED.tie_lines_json
            """,
            step["workspace_id"],
            row["id"],
            step["job_id"],
            result.matched_line_id,
            matching_mode,
            result.max_matched_ply,
            result.deviation_ply_self,
            result.deviation_ply_opp,
            compliance,
            who_left_first(result.deviation_ply_opp, result.deviation_ply_self),
            json.dumps(result.tie_line_ids),
        )
        matched += 1
    return matched


async def _copy_active_matches(conn: asyncpg.Connection, step: dict[str, Any]) -> int:
    active_run_id = await conn.fetchval(
        "SELECT active_analysis_run_id FROM workspace_state WHERE workspace_id=$1::uuid",
        step["workspace_id"],
    )
    if active_run_id is None:
        return 0
    result = await conn.execute(
        """
        INSERT INTO matches(
            workspace_id, game_id, analysis_run_id, matched_line_id, matching_mode,
            max_matched_ply, deviation_ply_you, deviation_ply_opp, compliance,
            who_left_first, recovered_to_rep, opponent_dev_to_known, tags_json, tie_lines_json
        )
        SELECT workspace_id, game_id, $2::uuid, matched_line_id, matching_mode,
               max_matched_ply, deviation_ply_you, deviation_ply_opp, compliance,
               who_left_first, recovered_to_rep, opponent_dev_to_known, tags_json, tie_lines_json
        FROM matches
        WHERE workspace_id=$1::uuid AND analysis_run_id=$3::uuid
        ON CONFLICT (workspace_id, analysis_run_id, game_id) DO NOTHING
        """,
        step["workspace_id"], step["job_id"], active_run_id,
    )
    return int(result.rsplit(" ", 1)[-1])


async def execute_orchestration_step(conn: asyncpg.Connection, redis, step: dict[str, Any]) -> dict[str, Any]:
    job = await jobs.get_job(conn, step["job_id"], step["workspace_id"])
    if job is None:
        raise ValueError(f"Job {step['job_id']} was not found.")
    if job["job_type"] not in ANALYSIS_JOB_TYPES:
        raise ValueError(f"Unsupported orchestration job: {job['job_type']}")
    locked = await conn.fetchval(
        "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
        step["workspace_id"],
    )
    if not locked:
        raise RuntimeError("A conflicting analysis job is already mutating this workspace.")
    try:
        requested_game_id = job["request"].get("game_id")
        game_id = int(requested_game_id) if requested_game_id is not None else None
        settings_snapshot = job["request"].get("settings_snapshot") or {}
        analysis_depth = int(settings_snapshot.get("engine_depth") or SETTINGS.stockfish_depth)
        max_plies = int(settings_snapshot.get("max_plies") or 30)
        matching_mode = str(settings_snapshot.get("matching_mode") or "STRICT").upper()
        engine_profile = job["request"].get("engine_profile") or {}
        engine_id = str(engine_profile.get("engine_id") or SETTINGS.stockfish_engine_id)
        artifact_ids: list[str] | None = None
        game_ids = [int(value) for value in job["request"].get("game_ids_snapshot", [])]
        copied = 0
        if job["job_type"] in {
            "engine-only-analysis", "incremental-analysis", "per-game-reanalysis"
        }:
            copied = await _copy_active_matches(conn, step)
        if job["job_type"] == "incremental-analysis":
            active_request = await conn.fetchval(
                """
                SELECT job.request_json
                FROM workspace_state state
                JOIN analysis_jobs job ON job.id=state.active_analysis_run_id
                WHERE state.workspace_id=$1::uuid
                """,
                step["workspace_id"],
            )
            if isinstance(active_request, str):
                active_request = json.loads(active_request)
            previous = set((active_request or {}).get("source_artifact_ids") or [])
            new_artifacts = [
                artifact for artifact in job["request"].get("source_artifacts", [])
                if str(artifact.get("id")) not in previous
            ]
            # A repertoire change can alter every match. New game artifacts only
            # require matching and engine work for those newly persisted games.
            artifact_ids = None if any(
                artifact.get("source_type") == "repertoire" for artifact in new_artifacts
            ) else [
                str(artifact["id"]) for artifact in new_artifacts
                if artifact.get("source_type") == "game"
            ]
        matched = 0
        if job["job_type"] not in {"engine-only-analysis", "review-insight-regeneration"}:
            matched = await _match_games(
                conn, step, game_id, artifact_ids, game_ids, matching_mode
            )
        scheduled = 0
        if job["job_type"] not in {"line-matching-reanalysis", "review-insight-regeneration"}:
            scheduled = await _schedule_engine_positions(
                conn, redis, step, game_id, artifact_ids, game_ids,
                analysis_depth, max_plies, engine_id
            )
        return {"games_copied": copied, "games_matched": matched, "engine_steps_scheduled": scheduled}
    finally:
        await conn.execute(
            "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
            step["workspace_id"],
        )
