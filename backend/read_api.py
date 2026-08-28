from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import asyncpg

from pathlib import Path

from backend.settings import SETTINGS, RuntimeFieldError, load_runtime_settings, update_runtime_settings
from analysis import statistics
from storage import queries

TIME_USAGE_PIVOTS = {"self_vs_opp", "in_book_vs_out_of_book"}
RATING_BAND_MIN_SIZE = 50
RATING_BAND_MAX_SIZE = 400
RATING_BAND_STEP = 50
RATING_BAND_DEFAULT_SIZE = 100
ALLOWED_RATING_BAND_SIZES = list(range(RATING_BAND_MIN_SIZE, RATING_BAND_MAX_SIZE + RATING_BAND_STEP, RATING_BAND_STEP))


def _validate_time_usage_pivot(pivot: str) -> str:
    if pivot not in TIME_USAGE_PIVOTS:
        raise ValueError(f"Invalid time usage pivot: {pivot}")
    return pivot


def normalize_rating_band_size(band_size: int) -> int:
    if band_size < RATING_BAND_MIN_SIZE or band_size > RATING_BAND_MAX_SIZE:
        return RATING_BAND_DEFAULT_SIZE
    if (band_size - RATING_BAND_MIN_SIZE) % RATING_BAND_STEP != 0:
        return RATING_BAND_DEFAULT_SIZE
    return band_size


def rating_band_guardrails_payload() -> dict[str, int | list[int]]:
    return {
        "min": RATING_BAND_MIN_SIZE,
        "max": RATING_BAND_MAX_SIZE,
        "step": RATING_BAND_STEP,
        "allowed_band_sizes": ALLOWED_RATING_BAND_SIZES,
    }


def _compute_percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    index = int((len(values) - 1) * quantile)
    return values[index]


def get_runtime_settings_payload(settings_ini_path: Path) -> dict[str, Any]:
    return load_runtime_settings(settings_ini_path)


def save_runtime_settings_payload(
    settings_ini_path: Path, payload: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[RuntimeFieldError]]:
    return update_runtime_settings(settings_ini_path, payload)


def _normalize_analysis_run_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        source = entry
    else:
        source = {
            "run_id": getattr(entry, "run_id", None) or getattr(entry, "job_id", None),
            "run_type": getattr(entry, "run_type", None),
            "status": getattr(entry, "status", None) or getattr(entry, "state", None),
            "started_at": getattr(entry, "started_at", None),
            "finished_at": getattr(entry, "finished_at", None),
            "error_reason": getattr(entry, "error_reason", None) or getattr(entry, "error", None),
        }

    raw_status = str(source.get("status") or source.get("state") or "running").strip().lower()
    status = raw_status if raw_status in {"running", "completed", "failed"} else "running"

    return {
        "run_id": str(source.get("run_id") or source.get("job_id") or ""),
        "run_type": str(source.get("run_type") or ""),
        "status": status,
        "started_at": str(source.get("started_at") or ""),
        "finished_at": source.get("finished_at"),
        "error_reason": source.get("error_reason") or source.get("error"),
    }


def _analysis_run_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    started_at = str(row.get("started_at") or "").strip()
    parsed_started_at = None
    if started_at:
        try:
            parsed_started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except ValueError:
            parsed_started_at = None

    if parsed_started_at is not None:
        return (parsed_started_at.isoformat(), str(row.get("run_id") or ""))
    return (started_at, str(row.get("run_id") or ""))


def normalize_analysis_runs(entries: list[Any], limit: int = 10) -> list[dict[str, Any]]:
    bounded_limit = min(max(limit, 1), 50)
    normalized = [_normalize_analysis_run_entry(entry) for entry in entries]
    normalized.sort(key=_analysis_run_sort_key, reverse=True)
    return normalized[:bounded_limit]


async def fetch_analysis_runs(runtime: Any, limit: int = 10) -> dict[str, Any]:
    runtime_payload = runtime.runs(limit=50)
    entries = list(getattr(runtime_payload, "runs", []))
    return {"runs": normalize_analysis_runs(entries, limit=limit)}


def _normalize_tree_repertoire_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "uci_move": str(row.get("uci_move") or ""),
        "san_move": row.get("san_move"),
        "next_pos_id": row.get("next_pos_id"),
        "weight": int(row.get("weight") or 0),
        "is_priority_edge": int(row.get("is_priority_edge") or 0),
        "is_user_mainline": int(row.get("is_user_mainline") or 0),
        "is_sideline_pending": int(row.get("is_sideline_pending") or 0),
    }


def _normalize_tree_game_row(row: dict[str, Any]) -> dict[str, Any]:
    games = int(row.get("games") or 0)
    wins = int(row.get("wins") or 0)
    draws = int(row.get("draws") or 0)
    losses = int(row.get("losses") or 0)
    score_pct = row.get("score_pct")
    if score_pct is None:
        score_pct = ((wins + 0.5 * draws) / games * 100.0) if games > 0 else 0.0
    return {
        "uci_move": str(row.get("uci_move") or ""),
        "san_move": row.get("san_move"),
        "next_pos_id": row.get("next_pos_id"),
        "games": games,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "avg_opp_elo": _safe_float(row.get("avg_opp_elo")),
        "score_pct": float(score_pct or 0.0),
    }


def build_tree_contract_payload(
    *,
    pos_id: int,
    my_side_only: bool,
    repertoire_rows: list[dict[str, Any]],
    game_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    repertoire_children = [_normalize_tree_repertoire_row(row) for row in repertoire_rows]
    game_children = [_normalize_tree_game_row(row) for row in game_rows]
    rep_moves = {row["uci_move"] for row in repertoire_children if row["uci_move"]}
    game_moves = {row["uci_move"] for row in game_children if row["uci_move"]}
    covered_by_games = len(rep_moves & game_moves)
    total_repertoire_moves = len(rep_moves)
    coverage_pct = (covered_by_games / total_repertoire_moves * 100.0) if total_repertoire_moves else 0.0
    top_repertoire_branches = sorted(repertoire_children, key=lambda row: int(row.get("weight") or 0), reverse=True)[:10]
    top_game_branches = sorted(game_children, key=lambda row: int(row.get("games") or 0), reverse=True)[:10]
    return {
        "pos_id": int(pos_id),
        "my_side_only": bool(my_side_only),
        "repertoire_children": repertoire_children,
        "game_children": game_children,
        "total_repertoire_moves": total_repertoire_moves,
        "covered_by_games": covered_by_games,
        "coverage_pct": float(coverage_pct),
        "top_repertoire_branches": top_repertoire_branches,
        "top_game_branches": top_game_branches,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_position_intelligence_payload(
    *,
    pos_id: int,
    my_side_only: bool,
    repertoire_rows: list[dict[str, Any]],
    game_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    tree = build_tree_contract_payload(
        pos_id=pos_id,
        my_side_only=my_side_only,
        repertoire_rows=repertoire_rows,
        game_rows=game_rows,
    )
    position = dict(summary.get("position") or {})
    totals = dict(summary.get("totals") or {})
    evals = dict(summary.get("evals") or {})
    latest_engine = summary.get("latest_engine") if isinstance(summary.get("latest_engine"), dict) else None
    recent_games = list(summary.get("recent_games") or [])

    games = int(totals.get("games") or 0)
    wins = int(totals.get("wins") or 0)
    draws = int(totals.get("draws") or 0)
    losses = int(totals.get("losses") or 0)
    score_pct = ((wins + 0.5 * draws) / games * 100.0) if games > 0 else 0.0
    repertoire_moves = {row["uci_move"] for row in tree["repertoire_children"] if row.get("uci_move")}
    game_moves = {row["uci_move"] for row in tree["game_children"] if row.get("uci_move")}
    deviations = [row for row in tree["game_children"] if row.get("uci_move") and row.get("uci_move") not in repertoire_moves]

    reasons: list[str] = []
    if games:
        reasons.append(f"{games} recent-game samples reach this position")
    if deviations:
        reasons.append(f"{sum(int(row.get('games') or 0) for row in deviations)} games deviate from repertoire moves")
    if tree["total_repertoire_moves"]:
        reasons.append(f"{tree['covered_by_games']} of {tree['total_repertoire_moves']} repertoire continuations are covered by games")
    if _safe_float(evals.get("avg_your_cpl")) is not None:
        reasons.append("Persisted move analysis includes CPL evidence")

    return {
        "pos_id": int(pos_id),
        "my_side_only": bool(my_side_only),
        "position": {
            "pos_id": int(position.get("pos_id") or pos_id),
            "fen": position.get("fen"),
            "side_to_move": position.get("side_to_move"),
        },
        "repertoire_continuations": tree["repertoire_children"],
        "game_continuations": tree["game_children"],
        "coverage": {
            "total_repertoire_moves": tree["total_repertoire_moves"],
            "covered_by_games": tree["covered_by_games"],
            "coverage_pct": tree["coverage_pct"],
            "total_games": games,
            "opponent_deviation_count": int(totals.get("opponent_deviation_count") or 0),
            "played_repertoire_moves": len(repertoire_moves & game_moves),
            "played_non_repertoire_moves": len(game_moves - repertoire_moves),
        },
        "outcome_summary": {
            "games": games,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "score_pct": float(score_pct),
        },
        "evaluation_summary": {
            "avg_exit_eval_cp": _safe_float(evals.get("avg_exit_eval_cp")),
            "avg_your_cpl": _safe_float(evals.get("avg_your_cpl")),
            "avg_rep_cpl": _safe_float(evals.get("avg_rep_cpl")),
            "latest_eval_cp": _safe_float(latest_engine.get("eval_cp")) if latest_engine else None,
            "best_uci": latest_engine.get("best_uci") if latest_engine else None,
            "depth": latest_engine.get("depth") if latest_engine else None,
            "engine_id": latest_engine.get("engine_id") if latest_engine else None,
        },
        "recent_games": recent_games,
        "evidence": {
            "repertoire_move_count": len(repertoire_moves),
            "game_move_count": len(game_moves),
            "recent_game_count": len(recent_games),
            "matters": reasons,
        },
    }


def _normalize_source_ref(ref: Any) -> dict[str, str] | None:
    if not isinstance(ref, dict):
        return None

    ref_type = str(ref.get("type") or "").strip()
    ref_id = str(ref.get("id") or "").strip()
    label = str(ref.get("label") or "").strip()
    if not ref_type or not ref_id:
        return None
    if not label:
        label = f"{ref_type}:{ref_id}"
    return {"type": ref_type, "id": ref_id, "label": label}


def _normalize_insight_row(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    refs = payload.get("source_refs") if isinstance(payload, dict) else None
    normalized_refs: list[dict[str, str]] = []
    if isinstance(refs, list):
        normalized_refs = [normalized for ref in refs if (normalized := _normalize_source_ref(ref)) is not None]
    data["priority_score"] = float(payload.get("priority_score") or 0) if isinstance(payload, dict) else 0.0
    data["confidence"] = float(payload.get("confidence") or 0) if isinstance(payload, dict) else 0.0
    data["source_refs"] = normalized_refs
    return data


def _sort_insights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("priority_score") or 0),
            float(row.get("confidence") or 0),
            str(row.get("title") or ""),
        ),
        reverse=True,
    )


def _sqlite_backend_allowed() -> bool:
    return not SETTINGS.is_production_environment


def _raise_sqlite_disabled() -> None:
    raise RuntimeError(
        "SQLite backend is disabled in production. Set DATA_BACKEND=postgres and configure POSTGRES_DSN."
    )


def _apply_games_filters(
    rows: list[dict[str, Any]],
    *,
    result: str | None = None,
    compliance: str | None = None,
    line_id: str | None = None,
    player: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    compliance_min: float | None = None,
) -> list[dict[str, Any]]:
    filtered = rows
    if result:
        filtered = [row for row in filtered if str(row.get("result") or "").casefold() == result.casefold()]
    if compliance:
        filtered = [row for row in filtered if str(row.get("compliance") or "").casefold() == compliance.casefold()]
    if line_id:
        filtered = [row for row in filtered if str(row.get("line_id") or "").casefold() == line_id.casefold()]
    if player:
        player_key = player.casefold()
        filtered = [
            row
            for row in filtered
            if player_key in str(row.get("white") or "").casefold() or player_key in str(row.get("black") or "").casefold()
        ]
    if date_from:
        filtered = [row for row in filtered if (row.get("date") or "") >= date_from]
    if date_to:
        filtered = [row for row in filtered if (row.get("date") or "") <= date_to]
    if compliance_min is not None:
        compliance_score = {
            "FULLY_COMPLIANT": 1.0,
            "PARTIALLY_COMPLIANT": 0.5,
            "NON_COMPLIANT": 0.0,
        }
        filtered = [
            row
            for row in filtered
            if compliance_score.get(str(row.get("compliance") or "").upper(), 0.0) >= compliance_min
        ]
    return filtered


def _sort_games(rows: list[dict[str, Any]], sort_by: str, sort_dir: str) -> list[dict[str, Any]]:
    reverse = sort_dir.lower() == "desc"

    if sort_by == "date":
        return sorted(rows, key=lambda row: (row.get("date") or "", row.get("id") or 0), reverse=reverse)
    if sort_by == "compliance":
        return sorted(
            rows,
            key=lambda row: (row.get("compliance") or "", row.get("date") or "", row.get("id") or 0),
            reverse=reverse,
        )
    if sort_by == "result":
        return sorted(
            rows,
            key=lambda row: (row.get("result") or "", row.get("date") or "", row.get("id") or 0),
            reverse=reverse,
        )
    return sorted(rows, key=lambda row: row.get("id") or 0, reverse=reverse)


def _normalize_games_sort(sort_by: str | None, sort_dir: str | None) -> tuple[str, str]:
    normalized_sort_by = (sort_by or "date").lower()
    if normalized_sort_by not in {"date", "result", "compliance", "id"}:
        normalized_sort_by = "date"

    normalized_sort_dir = (sort_dir or "desc").lower()
    if normalized_sort_dir not in {"asc", "desc"}:
        normalized_sort_dir = "desc"
    return normalized_sort_by, normalized_sort_dir


def _normalize_compliance_min(compliance_min: float | None) -> float | None:
    if compliance_min is None:
        return None
    return min(max(float(compliance_min), 0.0), 1.0)


def _build_game_navigation_payload(
    *,
    game_id: int,
    moves: list[dict[str, Any]],
    prev_game_id: int | None,
    next_game_id: int | None,
    navigation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    has_moves = len(moves) > 0
    raw_bookmarked = None
    if isinstance(navigation, dict):
        raw_bookmarked = navigation.get("bookmarked_ply_ids")

    if raw_bookmarked is None:
        raw_bookmarked = [move.get("ply") for move in moves if move.get("is_bookmarked")]

    bookmarked_ply_ids: list[int] = []
    if isinstance(raw_bookmarked, list):
        for value in raw_bookmarked:
            try:
                ply = int(value)
            except (TypeError, ValueError):
                continue
            if ply > 0 and ply not in bookmarked_ply_ids:
                bookmarked_ply_ids.append(ply)

    if isinstance(navigation, dict):
        current_game_id = navigation.get("current_game_id")
        if current_game_id is None:
            current_game_id = game_id
        can_jump_start = navigation.get("can_jump_start")
        can_jump_end = navigation.get("can_jump_end")
    else:
        current_game_id = game_id
        can_jump_start = None
        can_jump_end = None

    return {
        "current_game_id": int(current_game_id) if current_game_id is not None else int(game_id),
        "prev_game_id": prev_game_id,
        "next_game_id": next_game_id,
        "bookmarked_ply_ids": bookmarked_ply_ids,
        "can_jump_start": bool(can_jump_start) if isinstance(can_jump_start, bool) else has_moves,
        "can_jump_end": bool(can_jump_end) if isinstance(can_jump_end, bool) else has_moves,
    }


def _fetch_games_sqlite(
    limit: int,
    offset: int,
    *,
    result: str | None = None,
    compliance: str | None = None,
    line_id: str | None = None,
    player: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    compliance_min: float | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()

    import sqlite3

    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = queries.fetch_game_overview(conn)
    filtered = _apply_games_filters(
        rows,
        result=result,
        compliance=compliance,
        line_id=line_id,
        player=player,
        date_from=date_from,
        date_to=date_to,
        compliance_min=compliance_min,
    )
    sorted_rows = _sort_games(filtered, sort_by=sort_by, sort_dir=sort_dir)
    return sorted_rows[offset : offset + limit]


def _fetch_game_detail_sqlite(game_id: int) -> dict[str, Any] | None:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()

    import sqlite3

    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        header = queries.fetch_game_header(conn, game_id)
        if header is None:
            return None
        moves = queries.fetch_game_moves(conn, game_id)
        neighbors = conn.execute(
            """
            SELECT prev_game_id, next_game_id, prev_game_label, next_game_label
            FROM (
                SELECT
                    id,
                    LAG(id) OVER (ORDER BY date DESC, id DESC) AS prev_game_id,
                    LEAD(id) OVER (ORDER BY date DESC, id DESC) AS next_game_id,
                    LAG(
                        TRIM(
                            COALESCE(white, '?') || ' vs ' || COALESCE(black, '?')
                            || CASE WHEN date IS NOT NULL AND TRIM(date) <> '' THEN ' (' || date || ')' ELSE '' END
                        )
                    ) OVER (ORDER BY date DESC, id DESC) AS prev_game_label,
                    LEAD(
                        TRIM(
                            COALESCE(white, '?') || ' vs ' || COALESCE(black, '?')
                            || CASE WHEN date IS NOT NULL AND TRIM(date) <> '' THEN ' (' || date || ')' ELSE '' END
                        )
                    ) OVER (ORDER BY date DESC, id DESC) AS next_game_label
                FROM games
            ) ordered_games
            WHERE id = ?
            """,
            (game_id,),
        ).fetchone()

        pos_ids = sorted({int(move["pos_id"]) for move in moves if move.get("pos_id") is not None})
        fen_by_pos: dict[int, str] = {}
        if pos_ids:
            placeholders = ",".join("?" for _ in pos_ids)
            rows = conn.execute(
                f"SELECT id, fen_norm FROM positions WHERE id IN ({placeholders})",
                tuple(pos_ids),
            ).fetchall()
            fen_by_pos = {int(row["id"]): row["fen_norm"] for row in rows}

        enriched_moves = []
        for move in moves:
            enriched = dict(move)
            pos_id = move.get("pos_id")
            enriched["fen"] = fen_by_pos.get(int(pos_id)) if pos_id is not None else None
            enriched_moves.append(enriched)

    prev_game_id = int(neighbors["prev_game_id"]) if neighbors and neighbors["prev_game_id"] is not None else None
    next_game_id = int(neighbors["next_game_id"]) if neighbors and neighbors["next_game_id"] is not None else None
    return {
        "header": header,
        "moves": enriched_moves,
        "prev_game_id": prev_game_id,
        "next_game_id": next_game_id,
        "prev_game_label": str(neighbors["prev_game_label"]) if neighbors and neighbors["prev_game_label"] else None,
        "next_game_label": str(neighbors["next_game_label"]) if neighbors and neighbors["next_game_label"] else None,
        "navigation": _build_game_navigation_payload(
            game_id=game_id,
            moves=enriched_moves,
            prev_game_id=prev_game_id,
            next_game_id=next_game_id,
        ),
    }


async def _fetch_games_postgres(
    limit: int,
    offset: int,
    *,
    result: str | None = None,
    compliance: str | None = None,
    line_id: str | None = None,
    player: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    compliance_min: float | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.time_control,
                   g.white_elo, g.black_elo,
                   m.matched_line_id AS line_id,
                   m.compliance,
                   m.max_matched_ply,
                   m.matching_mode,
                   m.who_left_first,
                   (
                       SELECT SUM(CASE WHEN gp.repertoire_class = 'IN_REPERTOIRE_MAIN' THEN 1 ELSE 0 END)
                       FROM game_positions gp
                       WHERE gp.game_id = g.id AND gp.is_self = 1
                   ) AS in_main,
                   (
                       SELECT SUM(CASE WHEN gp.repertoire_class = 'IN_REPERTOIRE_OTHER' THEN 1 ELSE 0 END)
                       FROM game_positions gp
                       WHERE gp.game_id = g.id AND gp.is_self = 1
                   ) AS in_other,
                   (
                       SELECT SUM(CASE WHEN gp.repertoire_class = 'OUT_OF_REPERTOIRE' THEN 1 ELSE 0 END)
                       FROM game_positions gp
                       WHERE gp.game_id = g.id AND gp.is_self = 1
                   ) AS out_rep
            FROM games g
            LEFT JOIN matches m ON g.id = m.game_id
            """
        )
        filtered = _apply_games_filters(
            [dict(row) for row in rows],
            result=result,
            compliance=compliance,
            line_id=line_id,
            player=player,
            date_from=date_from,
            date_to=date_to,
            compliance_min=compliance_min,
        )
        sorted_rows = _sort_games(filtered, sort_by=sort_by, sort_dir=sort_dir)
        return sorted_rows[offset : offset + limit]
    finally:
        await conn.close()


async def _fetch_game_detail_postgres(game_id: int) -> dict[str, Any] | None:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        header = await conn.fetchrow(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.player_color,
                   g.white_elo, g.black_elo, g.time_control,
                   m.matched_line_id AS line_id,
                   m.max_matched_ply,
                   m.deviation_ply_you,
                   m.deviation_ply_opp,
                   m.matching_mode,
                   m.compliance,
                   m.who_left_first,
                   m.tie_lines_json,
                   m.tags_json
            FROM games g
            LEFT JOIN matches m ON g.id = m.game_id
            WHERE g.id = $1
            """,
            game_id,
        )
        if header is None:
            return None

        header_data = dict(header)
        header_data["tie_lines"] = header_data.get("tie_lines_json") or []
        header_data["tags"] = header_data.get("tags_json") or []

        moves = await conn.fetch(
            """
            SELECT gp.ply, gp.pos_id, p.fen_norm AS fen, gp.san_move, gp.uci_move, gp.repertoire_class, gp.is_self,
                   gp.clock_seconds, gp.time_spent_seconds, gp.time_spent_fraction,
                   ap.pre_eval_cp, ap.post_eval_cp, ap.best_uci, ap.your_cpl, ap.rep_cpl,
                   ap.quality_label
            FROM game_positions gp
            LEFT JOIN analysis_ply ap ON gp.game_id = ap.game_id AND gp.ply = ap.ply
            LEFT JOIN positions p ON gp.pos_id = p.id
            WHERE gp.game_id = $1
            ORDER BY gp.ply
            """,
            game_id,
        )
        neighbors = await conn.fetchrow(
            """
            SELECT prev_game_id, next_game_id, prev_game_label, next_game_label
            FROM (
                SELECT
                    id,
                    LAG(id) OVER (ORDER BY date DESC, id DESC) AS prev_game_id,
                    LEAD(id) OVER (ORDER BY date DESC, id DESC) AS next_game_id,
                    LAG(
                        TRIM(
                            COALESCE(white, '?') || ' vs ' || COALESCE(black, '?')
                            || CASE WHEN date IS NOT NULL AND BTRIM(date) <> '' THEN ' (' || date || ')' ELSE '' END
                        )
                    ) OVER (ORDER BY date DESC, id DESC) AS prev_game_label,
                    LEAD(
                        TRIM(
                            COALESCE(white, '?') || ' vs ' || COALESCE(black, '?')
                            || CASE WHEN date IS NOT NULL AND BTRIM(date) <> '' THEN ' (' || date || ')' ELSE '' END
                        )
                    ) OVER (ORDER BY date DESC, id DESC) AS next_game_label
                FROM games
            ) ordered_games
            WHERE id = $1
            """,
            game_id,
        )
        serialized_moves = [dict(row) for row in moves]
        prev_game_id = int(neighbors["prev_game_id"]) if neighbors and neighbors["prev_game_id"] is not None else None
        next_game_id = int(neighbors["next_game_id"]) if neighbors and neighbors["next_game_id"] is not None else None
        return {
            "header": header_data,
            "moves": serialized_moves,
            "prev_game_id": prev_game_id,
            "next_game_id": next_game_id,
            "prev_game_label": str(neighbors["prev_game_label"]) if neighbors and neighbors["prev_game_label"] else None,
            "next_game_label": str(neighbors["next_game_label"]) if neighbors and neighbors["next_game_label"] else None,
            "navigation": _build_game_navigation_payload(
                game_id=game_id,
                moves=serialized_moves,
                prev_game_id=prev_game_id,
                next_game_id=next_game_id,
            ),
        }
    finally:
        await conn.close()


async def fetch_games(
    limit: int,
    offset: int,
    *,
    result: str | None = None,
    compliance: str | None = None,
    line_id: str | None = None,
    player: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    compliance_min: float | None = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    normalized_sort_by, normalized_sort_dir = _normalize_games_sort(sort_by, sort_dir)
    normalized_compliance_min = _normalize_compliance_min(compliance_min)

    if SETTINGS.data_backend == "postgres":
        return await _fetch_games_postgres(
            limit,
            offset,
            result=result,
            compliance=compliance,
            line_id=line_id,
            player=player,
            date_from=date_from,
            date_to=date_to,
            compliance_min=normalized_compliance_min,
            sort_by=normalized_sort_by,
            sort_dir=normalized_sort_dir,
        )
    return await asyncio.to_thread(
        _fetch_games_sqlite,
        limit,
        offset,
        result=result,
        compliance=compliance,
        line_id=line_id,
        player=player,
        date_from=date_from,
        date_to=date_to,
        compliance_min=normalized_compliance_min,
        sort_by=normalized_sort_by,
        sort_dir=normalized_sort_dir,
    )


async def fetch_game_detail(game_id: int) -> dict[str, Any] | None:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_game_detail_postgres(game_id)
    return await asyncio.to_thread(_fetch_game_detail_sqlite, game_id)


def _fetch_overview_summary_sqlite() -> dict[str, Any]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()

    import sqlite3

    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        lines = conn.execute("SELECT COUNT(*) FROM repertoire_lines").fetchone()[0]
        games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        compliant = conn.execute("SELECT COUNT(*) FROM matches WHERE compliance = 'FULLY_COMPLIANT'").fetchone()[0]
        manual_priority = conn.execute("SELECT COUNT(*) FROM repertoire_lines WHERE is_priority = 1").fetchone()[0]
        auto_priority = conn.execute("SELECT COUNT(*) FROM trainer_line_state WHERE auto_priority_score > 0").fetchone()[0]
    return {
        "lines": int(lines),
        "manual_priority": int(manual_priority),
        "auto_priority": int(auto_priority),
        "games": int(games),
        "matched": int(matches),
        "fully_compliant": int(compliant),
    }


def _stats_not_supported_for_postgres() -> None:
    raise RuntimeError(
        "Stats endpoints are currently implemented for SQLite data backend. "
        "Use DATA_BACKEND=sqlite locally until Postgres parity endpoints are added."
    )


async def _fetch_overview_summary_postgres() -> dict[str, Any]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        lines = await conn.fetchval("SELECT COUNT(*) FROM repertoire_lines")
        games = await conn.fetchval("SELECT COUNT(*) FROM games")
        matches = await conn.fetchval("SELECT COUNT(*) FROM matches")
        compliant = await conn.fetchval("SELECT COUNT(*) FROM matches WHERE compliance = 'FULLY_COMPLIANT'")
        manual_priority = await conn.fetchval("SELECT COUNT(*) FROM repertoire_lines WHERE is_priority = TRUE")
        auto_priority = await conn.fetchval("SELECT COUNT(*) FROM trainer_line_state WHERE auto_priority_score > 0")
    finally:
        await conn.close()
    return {
        "lines": int(lines or 0),
        "manual_priority": int(manual_priority or 0),
        "auto_priority": int(auto_priority or 0),
        "games": int(games or 0),
        "matched": int(matches or 0),
        "fully_compliant": int(compliant or 0),
    }


async def _fetch_lines_stats_postgres() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        games = await conn.fetch(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.white_elo, g.black_elo,
                   g.player_color, g.is_daily, g.time_control,
                   m.matched_line_id AS line_id,
                   m.max_matched_ply,
                   m.deviation_ply_you,
                   m.deviation_ply_opp,
                   m.compliance,
                   m.matching_mode,
                   m.opponent_dev_to_known
            FROM games g
            LEFT JOIN matches m ON g.id = m.game_id
            """
        )
        eval_rows = await conn.fetch(
            """
            SELECT ap.game_id, ap.post_eval_cp
            FROM analysis_ply ap
            JOIN matches m ON ap.game_id = m.game_id AND ap.ply = m.max_matched_ply
            """
        )
        time_rows = await conn.fetch(
            """
            SELECT gp.game_id, gp.ply, gp.time_spent_seconds, gp.time_spent_fraction,
                   gp.is_self, g.is_daily, gp.repertoire_class, m.max_matched_ply
            FROM game_positions gp
            JOIN games g ON gp.game_id = g.id
            JOIN matches m ON gp.game_id = m.game_id
            WHERE gp.time_spent_seconds IS NOT NULL
            """
        )
        class_rows = await conn.fetch(
            """
            SELECT m.matched_line_id AS line_id,
                   SUM(CASE WHEN gp.is_self = TRUE AND gp.repertoire_class = 'IN_REPERTOIRE_OTHER' THEN 1 ELSE 0 END) AS in_other,
                   SUM(CASE WHEN gp.is_self = TRUE AND gp.repertoire_class IN ('IN_REPERTOIRE_MAIN', 'IN_REPERTOIRE_OTHER') THEN 1 ELSE 0 END) AS in_total,
                   SUM(CASE WHEN gp.is_self = TRUE AND gp.repertoire_class = 'OUT_OF_REPERTOIRE' THEN 1 ELSE 0 END) AS out_total
            FROM game_positions gp
            JOIN matches m ON gp.game_id = m.game_id
            WHERE m.matched_line_id IS NOT NULL
            GROUP BY m.matched_line_id
            """
        )
    finally:
        await conn.close()

    eval_at_exit = {int(row["game_id"]): row["post_eval_cp"] for row in eval_rows}
    time_by_game = statistics.time_analysis.compute_time_usage_by_game([dict(row) for row in time_rows])
    class_counts = {row["line_id"]: dict(row) for row in class_rows}

    stats: dict[str | None, dict[str, Any]] = {}
    for game in [dict(row) for row in games]:
        key = game.get("line_id")
        if key is None:
            continue
        entry = stats.setdefault(key, statistics._init_stat_entry())
        statistics._accumulate_game(entry, game, eval_at_exit, time_by_game)

    results = statistics._finalize_stats(stats)
    for result in results:
        counts = class_counts.get(result["key"] or None, {})
        in_other = counts.get("in_other") or 0
        in_total = counts.get("in_total") or 0
        result["in_rep_other_rate"] = in_other / in_total if in_total else None
    return results


async def _fetch_time_usage_stats_postgres() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        games = await conn.fetch(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.white_elo, g.black_elo,
                   g.player_color, g.is_daily, g.time_control,
                   m.matched_line_id AS line_id,
                   m.max_matched_ply,
                   m.deviation_ply_you,
                   m.deviation_ply_opp,
                   m.compliance,
                   m.matching_mode,
                   m.opponent_dev_to_known
            FROM games g
            LEFT JOIN matches m ON g.id = m.game_id
            """
        )
        eval_rows = await conn.fetch(
            """
            SELECT ap.game_id, ap.post_eval_cp
            FROM analysis_ply ap
            JOIN matches m ON ap.game_id = m.game_id AND ap.ply = m.max_matched_ply
            """
        )
        time_rows = await conn.fetch(
            """
            SELECT gp.game_id, gp.ply, gp.time_spent_seconds, gp.time_spent_fraction,
                   gp.is_self, g.is_daily, gp.repertoire_class, m.max_matched_ply
            FROM game_positions gp
            JOIN games g ON gp.game_id = g.id
            JOIN matches m ON gp.game_id = m.game_id
            WHERE gp.time_spent_seconds IS NOT NULL
            """
        )
    finally:
        await conn.close()

    eval_at_exit = {int(row["game_id"]): row["post_eval_cp"] for row in eval_rows}
    time_by_game = statistics.time_analysis.compute_time_usage_by_game([dict(row) for row in time_rows])

    stats: dict[str | None, dict[str, Any]] = {}
    for game in [dict(row) for row in games]:
        date = game.get("date") or ""
        month = date[:7] if len(date) >= 7 else "Unknown"
        entry = stats.setdefault(month, statistics._init_stat_entry())
        statistics._accumulate_game(entry, game, eval_at_exit, time_by_game)
    return statistics._finalize_stats(stats)


async def _fetch_rating_band_stats_postgres(band_size: int) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        games = await conn.fetch(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.white_elo, g.black_elo,
                   g.player_color, g.is_daily, g.time_control,
                   m.matched_line_id AS line_id,
                   m.max_matched_ply,
                   m.deviation_ply_you,
                   m.deviation_ply_opp,
                   m.compliance,
                   m.matching_mode,
                   m.opponent_dev_to_known
            FROM games g
            LEFT JOIN matches m ON g.id = m.game_id
            """
        )
        eval_rows = await conn.fetch(
            """
            SELECT ap.game_id, ap.post_eval_cp
            FROM analysis_ply ap
            JOIN matches m ON ap.game_id = m.game_id AND ap.ply = m.max_matched_ply
            """
        )
        time_rows = await conn.fetch(
            """
            SELECT gp.game_id, gp.ply, gp.time_spent_seconds, gp.time_spent_fraction,
                   gp.is_self, g.is_daily, gp.repertoire_class, m.max_matched_ply
            FROM game_positions gp
            JOIN games g ON gp.game_id = g.id
            JOIN matches m ON gp.game_id = m.game_id
            WHERE gp.time_spent_seconds IS NOT NULL
            """
        )
    finally:
        await conn.close()

    eval_at_exit = {int(row["game_id"]): row["post_eval_cp"] for row in eval_rows}
    time_by_game = statistics.time_analysis.compute_time_usage_by_game([dict(row) for row in time_rows])

    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for game in [dict(row) for row in games]:
        white_band = statistics._rating_band(game.get("white_elo"), band_size)
        black_band = statistics._rating_band(game.get("black_elo"), band_size)
        key = (white_band, black_band)
        entry = stats.setdefault(key, statistics._init_stat_entry())
        statistics._accumulate_game(entry, game, eval_at_exit, time_by_game)

    results = statistics._finalize_stats(stats)
    for result in results:
        key = result["key"]
        if isinstance(key, tuple):
            result["white_band"], result["black_band"] = key
        result.pop("key", None)
    return results


async def _fetch_insights_postgres() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT category, title, details, data_json
            FROM insights
            ORDER BY category, title
            """
        )
    finally:
        await conn.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        payload = data.get("data_json")
        if payload:
            try:
                data["data"] = json.loads(payload) if isinstance(payload, str) else payload
            except json.JSONDecodeError:
                data["data"] = None
        else:
            data["data"] = None
        results.append(_normalize_insight_row(data))
    return _sort_insights(results)


async def _fetch_review_items_postgres() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT line_id, reason, detail
            FROM review_items
            ORDER BY reason, line_id
            """
        )
    finally:
        await conn.close()
    return [dict(row) for row in rows]


def _fetch_lines_stats_sqlite() -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        return statistics.aggregate_by_line(conn)


def _fetch_time_usage_stats_sqlite() -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        return statistics.aggregate_by_month(conn)


def _fetch_rating_band_stats_sqlite(band_size: int) -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        return statistics.aggregate_by_rating_band(conn, band_size)


def _fetch_insights_sqlite() -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = queries.fetch_insights(conn)
    normalized = [_normalize_insight_row(dict(row)) for row in rows]
    return _sort_insights(normalized)


def _fetch_review_items_sqlite() -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        return queries.fetch_review_items(conn)


async def fetch_overview_summary() -> dict[str, Any]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_overview_summary_postgres()
    return await asyncio.to_thread(_fetch_overview_summary_sqlite)


async def fetch_lines_stats() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_lines_stats_postgres()
    return await asyncio.to_thread(_fetch_lines_stats_sqlite)


def _normalize_time_usage_payload(rows: list[dict[str, Any]], pivot: str) -> dict[str, Any]:
    buckets: list[dict[str, Any]] = []
    totals: dict[str, float | int] = {
        "total_games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
    }
    for row in rows:
        bucket = dict(row)
        bucket["bucket"] = bucket.pop("key", "Unknown")
        buckets.append(bucket)
        totals["total_games"] += int(bucket.get("total_games") or 0)
        totals["wins"] += int(bucket.get("wins") or 0)
        totals["losses"] += int(bucket.get("losses") or 0)
        totals["draws"] += int(bucket.get("draws") or 0)
    return {"pivot": pivot, "buckets": buckets, "totals": totals}


def _build_time_usage_stats_payload(
    games: list[dict[str, Any]],
    eval_at_exit: dict[int, int | None],
    time_rows: list[dict[str, Any]],
    pivot: str,
) -> dict[str, Any]:
    normalized_pivot = _validate_time_usage_pivot(pivot)

    game_totals = {
        "self_vs_opp": {"Self", "Opponent"},
        "in_book_vs_out_of_book": {"In book", "Out of book"},
    }
    bucket_game_ids: dict[str, set[int]] = {bucket: set() for bucket in game_totals[normalized_pivot]}
    bucket_totals: dict[str, dict[str, float | int]] = {
        bucket: {"total_moves": 0, "time_total_seconds": 0.0, "time_fraction_total": 0.0, "time_fraction_count": 0}
        for bucket in game_totals[normalized_pivot]
    }

    for row in time_rows:
        if row.get("is_daily"):
            continue
        time_spent = row.get("time_spent_seconds")
        if time_spent is None:
            continue
        if normalized_pivot == "self_vs_opp":
            bucket_name = "Self" if row.get("is_self") else "Opponent"
        else:
            if not row.get("is_self"):
                continue
            rep_class = row.get("repertoire_class") or ""
            bucket_name = "In book" if rep_class in {"IN_REPERTOIRE_MAIN", "IN_REPERTOIRE_OTHER"} else "Out of book"
        bucket_game_ids[bucket_name].add(int(row["game_id"]))
        bucket = bucket_totals[bucket_name]
        bucket["total_moves"] = int(bucket["total_moves"]) + 1
        bucket["time_total_seconds"] = float(bucket["time_total_seconds"]) + float(time_spent)
        fraction = row.get("time_spent_fraction")
        if fraction is not None:
            bucket["time_fraction_total"] = float(bucket["time_fraction_total"]) + float(fraction)
            bucket["time_fraction_count"] = int(bucket["time_fraction_count"]) + 1

    buckets: list[dict[str, Any]] = []
    for bucket_name in sorted(bucket_totals.keys()):
        bucket = bucket_totals[bucket_name]
        total_moves = int(bucket["total_moves"])
        fraction_count = int(bucket["time_fraction_count"])
        buckets.append(
            {
                "bucket": bucket_name,
                "total_games": len(bucket_game_ids[bucket_name]),
                "total_moves": total_moves,
                "avg_time_spent_seconds": (float(bucket["time_total_seconds"]) / total_moves) if total_moves else None,
                "avg_time_spent_fraction": (float(bucket["time_fraction_total"]) / fraction_count) if fraction_count else None,
            }
        )

    totals = {
        "total_games": len({int(game["id"]) for game in games}),
        "total_moves": sum(int(bucket["total_moves"]) for bucket in bucket_totals.values()),
    }
    return {"pivot": normalized_pivot, "buckets": buckets, "totals": totals}


def _fetch_time_usage_stats_sqlite(pivot: str) -> dict[str, Any]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3

    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        games = queries.fetch_game_summaries(conn)
        eval_at_exit = queries.fetch_eval_at_exit(conn)
        time_rows = queries.fetch_time_usage_rows(conn)

    return _build_time_usage_stats_payload(games, eval_at_exit, time_rows, pivot)


async def fetch_time_usage_stats(pivot: str) -> dict[str, Any]:
    normalized_pivot = _validate_time_usage_pivot(pivot)

    if SETTINGS.data_backend == "postgres":
        conn = await asyncpg.connect(SETTINGS.postgres_dsn)
        try:
            games = await conn.fetch(
                """
                SELECT g.id, g.date, g.white, g.black, g.result, g.white_elo, g.black_elo,
                       g.player_color, g.is_daily, g.time_control,
                       m.matched_line_id AS line_id,
                       m.max_matched_ply,
                       m.deviation_ply_you,
                       m.deviation_ply_opp,
                       m.compliance,
                       m.matching_mode,
                       m.opponent_dev_to_known
                FROM games g
                LEFT JOIN matches m ON g.id = m.game_id
                """
            )
            eval_rows = await conn.fetch(
                """
                SELECT ap.game_id, ap.post_eval_cp
                FROM analysis_ply ap
                JOIN matches m ON ap.game_id = m.game_id AND ap.ply = m.max_matched_ply
                """
            )
            time_rows = await conn.fetch(
                """
                SELECT gp.game_id, gp.ply, gp.time_spent_seconds, gp.time_spent_fraction,
                       gp.is_self, g.is_daily, gp.repertoire_class, m.max_matched_ply
                FROM game_positions gp
                JOIN games g ON gp.game_id = g.id
                JOIN matches m ON gp.game_id = m.game_id
                WHERE gp.time_spent_seconds IS NOT NULL
                """
            )
        finally:
            await conn.close()
        eval_at_exit = {int(row["game_id"]): row["post_eval_cp"] for row in eval_rows}
        return _build_time_usage_stats_payload(
            [dict(row) for row in games],
            eval_at_exit,
            [dict(row) for row in time_rows],
            normalized_pivot,
        )
    return await asyncio.to_thread(_fetch_time_usage_stats_sqlite, normalized_pivot)


async def fetch_line_stats_detail(line_id: str) -> dict[str, Any] | None:
    rows = await fetch_lines_stats()
    for row in rows:
        if str(row.get("key") or "") == line_id:
            detail = dict(row)
            detail["line_id"] = detail.pop("key")
            return detail
    return None


async def fetch_line_stats_history(line_id: str) -> dict[str, Any]:
    if SETTINGS.data_backend == "postgres":
        conn = await asyncpg.connect(SETTINGS.postgres_dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT g.date
                FROM games g
                JOIN matches m ON g.id = m.game_id
                WHERE m.matched_line_id = $1
                """,
                line_id,
            )
            games = [dict(row) for row in rows]
        finally:
            await conn.close()
    else:
        if not _sqlite_backend_allowed():
            _raise_sqlite_disabled()
        import sqlite3

        with sqlite3.connect(SETTINGS.sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT g.date
                FROM games g
                JOIN matches m ON g.id = m.game_id
                WHERE m.matched_line_id = ?
                """,
                (line_id,),
            ).fetchall()
            games = [dict(row) for row in rows]

    buckets: dict[str, dict[str, int | str]] = {}
    for game in games:
        date = game.get("date") or ""
        month = date[:7] if len(date) >= 7 else "Unknown"
        entry = buckets.setdefault(month, {"bucket": month, "total_games": 0})
        entry["total_games"] = int(entry.get("total_games") or 0) + 1

    bucket_list = sorted(buckets.values(), key=lambda item: str(item["bucket"]))
    total_games = sum(int(item["total_games"]) for item in bucket_list)
    return {
        "line_id": line_id,
        "buckets": bucket_list,
        "totals": {"total_games": total_games, "months": len(bucket_list)},
    }


async def fetch_rating_band_stats(band_size: int) -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_rating_band_stats_postgres(band_size)
    return await asyncio.to_thread(_fetch_rating_band_stats_sqlite, band_size)


async def fetch_rating_band_stats_payload(band_size: int) -> dict[str, Any]:
    normalized_band_size = normalize_rating_band_size(band_size)
    buckets = await fetch_rating_band_stats(normalized_band_size)
    total_games = sum(int(row.get("total_games") or 0) for row in buckets)
    compliance_rates = sorted(
        [float(row["compliance_rate"]) for row in buckets if row.get("compliance_rate") is not None]
    )
    payload = rating_band_guardrails_payload()
    return {
        "band_size": normalized_band_size,
        "allowed_band_sizes": payload["allowed_band_sizes"],
        "percentiles": {
            "p25_compliance_rate": _compute_percentile(compliance_rates, 0.25),
            "p50_compliance_rate": _compute_percentile(compliance_rates, 0.5),
            "p75_compliance_rate": _compute_percentile(compliance_rates, 0.75),
        },
        "totals": {"total_games": total_games, "bucket_count": len(buckets)},
        "buckets": buckets,
    }


async def fetch_insights() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_insights_postgres()
    return await asyncio.to_thread(_fetch_insights_sqlite)


async def fetch_review_items() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_review_items_postgres()
    return await asyncio.to_thread(_fetch_review_items_sqlite)
