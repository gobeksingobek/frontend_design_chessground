from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from backend.settings import SETTINGS


TIME_USAGE_PIVOTS = {"self_vs_opp", "in_book_vs_out_of_book"}
RATING_BAND_MIN_SIZE = 50
RATING_BAND_MAX_SIZE = 400
RATING_BAND_STEP = 50
RATING_BAND_DEFAULT_SIZE = 100
ALLOWED_RATING_BAND_SIZES = list(
    range(RATING_BAND_MIN_SIZE, RATING_BAND_MAX_SIZE + RATING_BAND_STEP, RATING_BAND_STEP)
)


def normalize_rating_band_size(band_size: int) -> int:
    if band_size not in ALLOWED_RATING_BAND_SIZES:
        return RATING_BAND_DEFAULT_SIZE
    return band_size


def normalize_analysis_runs(entries: list[Any], limit: int = 10) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        source = entry if isinstance(entry, dict) else vars(entry)
        raw_status = str(source.get("status") or source.get("state") or "running").lower()
        status = raw_status if raw_status in {"running", "completed", "failed"} else "running"
        normalized.append(
            {
                "run_id": str(source.get("run_id") or source.get("job_id") or ""),
                "run_type": str(source.get("run_type") or source.get("job_type") or ""),
                "status": status,
                "started_at": str(source.get("started_at") or ""),
                "finished_at": source.get("finished_at"),
                "error_reason": source.get("error_reason") or source.get("error"),
            }
        )
    normalized.sort(key=lambda row: (row["started_at"], row["run_id"]), reverse=True)
    return normalized[: min(max(limit, 1), 50)]


async def fetch_analysis_runs(runtime: Any, limit: int = 10) -> dict[str, Any]:
    payload = runtime.runs(limit=50)
    return {"runs": normalize_analysis_runs(list(getattr(payload, "runs", [])), limit)}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_tree_contract_payload(
    *,
    pos_id: int,
    my_side_only: bool,
    repertoire_rows: list[dict[str, Any]],
    game_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    repertoire_children = [
        {
            "uci_move": str(row.get("uci_move") or ""),
            "san_move": row.get("san_move"),
            "next_pos_id": row.get("next_pos_id"),
            "weight": int(row.get("weight") or 0),
            "is_priority_edge": int(row.get("is_priority_edge") or 0),
            "is_user_mainline": int(row.get("is_user_mainline") or 0),
            "is_sideline_pending": int(row.get("is_sideline_pending") or 0),
        }
        for row in repertoire_rows
    ]
    game_children: list[dict[str, Any]] = []
    for row in game_rows:
        games = int(row.get("games") or 0)
        wins = int(row.get("wins") or 0)
        draws = int(row.get("draws") or 0)
        game_children.append(
            {
                "uci_move": str(row.get("uci_move") or ""),
                "san_move": row.get("san_move"),
                "next_pos_id": row.get("next_pos_id"),
                "games": games,
                "wins": wins,
                "draws": draws,
                "losses": int(row.get("losses") or 0),
                "avg_opp_elo": _safe_float(row.get("avg_opp_elo")),
                "score_pct": float(row.get("score_pct") or ((wins + 0.5 * draws) / games * 100 if games else 0)),
            }
        )
    rep_moves = {row["uci_move"] for row in repertoire_children if row["uci_move"]}
    game_moves = {row["uci_move"] for row in game_children if row["uci_move"]}
    covered = len(rep_moves & game_moves)
    coverage = covered / len(rep_moves) * 100 if rep_moves else 0.0
    return {
        "pos_id": int(pos_id),
        "my_side_only": bool(my_side_only),
        "repertoire_children": repertoire_children,
        "game_children": game_children,
        "total_repertoire_moves": len(rep_moves),
        "covered_by_games": covered,
        "coverage_pct": float(coverage),
        "top_repertoire_branches": sorted(repertoire_children, key=lambda row: row["weight"], reverse=True)[:10],
        "top_game_branches": sorted(game_children, key=lambda row: row["games"], reverse=True)[:10],
    }


def build_position_intelligence_payload(
    *, pos_id: int, my_side_only: bool, repertoire_rows: list[dict[str, Any]],
    game_rows: list[dict[str, Any]], summary: dict[str, Any],
) -> dict[str, Any]:
    tree = build_tree_contract_payload(
        pos_id=pos_id, my_side_only=my_side_only,
        repertoire_rows=repertoire_rows, game_rows=game_rows,
    )
    totals = dict(summary.get("totals") or {})
    evals = dict(summary.get("evals") or {})
    position = dict(summary.get("position") or {})
    latest = summary.get("latest_engine") if isinstance(summary.get("latest_engine"), dict) else {}
    games = int(totals.get("games") or 0)
    wins = int(totals.get("wins") or 0)
    draws = int(totals.get("draws") or 0)
    losses = int(totals.get("losses") or 0)
    rep_moves = {row["uci_move"] for row in tree["repertoire_children"]}
    played_moves = {row["uci_move"] for row in tree["game_children"]}
    reasons: list[str] = []
    if games:
        reasons.append(f"{games} recent-game samples reach this position")
    if rep_moves:
        reasons.append(f"{tree['covered_by_games']} of {len(rep_moves)} repertoire continuations are covered by games")
    return {
        "pos_id": pos_id,
        "my_side_only": my_side_only,
        "position": {"pos_id": int(position.get("pos_id") or pos_id), "fen": position.get("fen"), "side_to_move": position.get("side_to_move")},
        "repertoire_continuations": tree["repertoire_children"],
        "game_continuations": tree["game_children"],
        "coverage": {
            "total_repertoire_moves": len(rep_moves), "covered_by_games": tree["covered_by_games"],
            "coverage_pct": tree["coverage_pct"], "total_games": games,
            "opponent_deviation_count": int(totals.get("opponent_deviation_count") or 0),
            "played_repertoire_moves": len(rep_moves & played_moves),
            "played_non_repertoire_moves": len(played_moves - rep_moves),
        },
        "outcome_summary": {"games": games, "wins": wins, "draws": draws, "losses": losses, "score_pct": (wins + 0.5 * draws) / games * 100 if games else 0.0},
        "evaluation_summary": {
            "avg_exit_eval_cp": _safe_float(evals.get("avg_exit_eval_cp")),
            "avg_your_cpl": _safe_float(evals.get("avg_your_cpl")),
            "avg_rep_cpl": _safe_float(evals.get("avg_rep_cpl")),
            "latest_eval_cp": _safe_float(latest.get("eval_cp")), "best_uci": latest.get("best_uci"),
            "depth": latest.get("depth"), "engine_id": latest.get("engine_id"),
        },
        "recent_games": list(summary.get("recent_games") or []),
        "evidence": {"repertoire_move_count": len(rep_moves), "game_move_count": len(played_moves), "recent_game_count": len(summary.get("recent_games") or []), "matters": reasons},
    }


def _normalize_source_ref(ref: Any) -> dict[str, str] | None:
    if not isinstance(ref, dict):
        return None
    kind, ref_id = str(ref.get("type") or "").strip(), str(ref.get("id") or "").strip()
    if not kind or not ref_id:
        return None
    return {"type": kind, "id": ref_id, "label": str(ref.get("label") or f"{kind}:{ref_id}")}


def _normalize_insight_row(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    refs = payload.get("source_refs") if isinstance(payload, dict) else []
    data["priority_score"] = float(payload.get("priority_score") or 0)
    data["confidence"] = float(payload.get("confidence") or 0)
    data["source_refs"] = [value for ref in refs if (value := _normalize_source_ref(ref)) is not None] if isinstance(refs, list) else []
    return data


def _sort_insights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (float(row.get("priority_score") or 0), float(row.get("confidence") or 0), str(row.get("title") or "")), reverse=True)


def _apply_games_filters(
    rows: list[dict[str, Any]], *, result: str | None = None, compliance: str | None = None,
    line_id: str | None = None, player: str | None = None, date_from: str | None = None,
    date_to: str | None = None, compliance_min: float | None = None,
) -> list[dict[str, Any]]:
    filtered = rows
    if result:
        filtered = [row for row in filtered if str(row.get("result") or "").casefold() == result.casefold()]
    if compliance:
        filtered = [row for row in filtered if str(row.get("compliance") or "").casefold() == compliance.casefold()]
    if line_id:
        filtered = [row for row in filtered if str(row.get("line_id") or "").casefold() == line_id.casefold()]
    if player:
        key = player.casefold()
        filtered = [row for row in filtered if key in str(row.get("white") or "").casefold() or key in str(row.get("black") or "").casefold()]
    if date_from:
        filtered = [row for row in filtered if str(row.get("date") or "") >= date_from]
    if date_to:
        filtered = [row for row in filtered if str(row.get("date") or "") <= date_to]
    if compliance_min is not None:
        scores = {"FULLY_COMPLIANT": 1.0, "PARTIALLY_COMPLIANT": 0.5}
        filtered = [row for row in filtered if scores.get(str(row.get("compliance") or "").upper(), 0.0) >= compliance_min]
    return filtered


def _normalize_games_sort(sort_by: str | None, sort_dir: str | None) -> tuple[str, str]:
    field = (sort_by or "date").lower()
    direction = (sort_dir or "desc").lower()
    return (field if field in {"date", "result", "compliance", "id"} else "date", direction if direction in {"asc", "desc"} else "desc")


def _normalize_compliance_min(value: float | None) -> float | None:
    return None if value is None else min(max(float(value), 0.0), 1.0)


def _sort_games(rows: list[dict[str, Any]], sort_by: str, sort_dir: str) -> list[dict[str, Any]]:
    reverse = sort_dir == "desc"
    return sorted(rows, key=lambda row: (row.get(sort_by) or "", row.get("id") or 0), reverse=reverse)


async def fetch_games(
    limit: int, offset: int, *, result: str | None = None, compliance: str | None = None,
    line_id: str | None = None, player: str | None = None, date_from: str | None = None,
    date_to: str | None = None, compliance_min: float | None = None,
    sort_by: str = "date", sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT g.id, g.date, g.white, g.black, g.result, g.time_control, g.white_elo, g.black_elo,
                   m.matched_line_id AS line_id, m.compliance, m.max_matched_ply, m.matching_mode, m.who_left_first,
                   COUNT(*) FILTER (WHERE COALESCE(ap.repertoire_class, gp.repertoire_class) = 'IN_REPERTOIRE_MAIN' AND gp.is_self = 1)::int AS in_main,
                   COUNT(*) FILTER (WHERE COALESCE(ap.repertoire_class, gp.repertoire_class) = 'IN_REPERTOIRE_OTHER' AND gp.is_self = 1)::int AS in_other,
                   COUNT(*) FILTER (WHERE COALESCE(ap.repertoire_class, gp.repertoire_class) = 'OUT_OF_REPERTOIRE' AND gp.is_self = 1)::int AS out_rep
            FROM games g
            LEFT JOIN workspace_state ws ON ws.workspace_id = g.workspace_id
            LEFT JOIN matches m ON m.workspace_id = g.workspace_id AND m.game_id = g.id
                 AND m.analysis_run_id = ws.active_analysis_run_id
            LEFT JOIN game_positions gp ON gp.workspace_id = g.workspace_id AND gp.game_id = g.id
            LEFT JOIN analysis_ply ap ON ap.workspace_id=g.workspace_id AND ap.game_id=g.id
                                     AND ap.ply=gp.ply AND ap.analysis_run_id=ws.active_analysis_run_id
            WHERE g.workspace_id = $1::uuid GROUP BY g.id, m.matched_line_id, m.compliance,
                 m.max_matched_ply, m.matching_mode, m.who_left_first
            """,
            SETTINGS.workspace_id,
        )
    finally:
        await conn.close()
    filtered = _apply_games_filters([dict(row) for row in rows], result=result, compliance=compliance, line_id=line_id, player=player, date_from=date_from, date_to=date_to, compliance_min=_normalize_compliance_min(compliance_min))
    field, direction = _normalize_games_sort(sort_by, sort_dir)
    return _sort_games(filtered, field, direction)[offset : offset + limit]


async def fetch_game_detail(game_id: int) -> dict[str, Any] | None:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        header = await conn.fetchrow(
            """
            SELECT g.*, m.matched_line_id AS line_id, m.max_matched_ply, m.deviation_ply_you,
                   m.deviation_ply_opp, m.matching_mode, m.compliance, m.who_left_first,
                   m.tie_lines_json, m.tags_json
            FROM games g
            LEFT JOIN workspace_state ws ON ws.workspace_id = g.workspace_id
            LEFT JOIN matches m ON m.workspace_id = g.workspace_id AND m.game_id = g.id
                 AND m.analysis_run_id = ws.active_analysis_run_id
            WHERE g.workspace_id = $1::uuid AND g.id = $2
            """, SETTINGS.workspace_id, game_id,
        )
        if not header:
            return None
        active_run = await conn.fetchval("SELECT active_analysis_run_id FROM workspace_state WHERE workspace_id = $1::uuid", SETTINGS.workspace_id)
        moves = await conn.fetch(
            """
            SELECT gp.*, p.fen_norm AS fen, ap.pre_eval_cp, ap.post_eval_cp, ap.best_uci,
                   ap.your_cpl, ap.rep_cpl, ap.quality_label,
                   COALESCE(ap.repertoire_class, gp.repertoire_class) AS derived_repertoire_class
            FROM game_positions gp JOIN positions p ON p.id = gp.pos_id
            LEFT JOIN analysis_ply ap ON ap.workspace_id = gp.workspace_id AND ap.game_id = gp.game_id
                 AND ap.ply = gp.ply AND ($3::uuid IS NULL OR ap.analysis_run_id = $3::uuid)
            WHERE gp.workspace_id = $1::uuid AND gp.game_id = $2 ORDER BY gp.ply
            """, SETTINGS.workspace_id, game_id, active_run,
        )
        neighbors = await conn.fetchrow(
            """
            WITH ordered AS (
              SELECT id, LAG(id) OVER (ORDER BY date DESC, id DESC) prev_game_id,
                     LEAD(id) OVER (ORDER BY date DESC, id DESC) next_game_id
              FROM games WHERE workspace_id = $1::uuid
            ) SELECT * FROM ordered WHERE id = $2
            """, SETTINGS.workspace_id, game_id,
        )
    finally:
        await conn.close()
    header_data = dict(header)
    header_data["tie_lines"] = header_data.get("tie_lines_json") or []
    header_data["tags"] = header_data.get("tags_json") or []
    prev_id = int(neighbors["prev_game_id"]) if neighbors and neighbors["prev_game_id"] is not None else None
    next_id = int(neighbors["next_game_id"]) if neighbors and neighbors["next_game_id"] is not None else None
    serialized = []
    for row in moves:
        item = dict(row)
        item["repertoire_class"] = item.pop("derived_repertoire_class", None)
        serialized.append(item)
    return {"header": header_data, "moves": serialized, "prev_game_id": prev_id, "next_game_id": next_id,
            "prev_game_label": None, "next_game_label": None,
            "navigation": {"current_game_id": game_id, "prev_game_id": prev_id, "next_game_id": next_id,
                           "bookmarked_ply_ids": [], "can_jump_start": bool(serialized), "can_jump_end": bool(serialized)}}


async def fetch_overview_summary() -> dict[str, Any]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        values = await conn.fetchrow(
            """
            SELECT (SELECT COUNT(*) FROM repertoire_lines WHERE workspace_id = $1::uuid) lines,
                   (SELECT COUNT(*) FROM repertoire_lines WHERE workspace_id = $1::uuid AND is_priority = 1) manual_priority,
                   (SELECT COUNT(*) FROM trainer_line_state WHERE workspace_id = $1::uuid AND auto_priority_score > 0) auto_priority,
                   (SELECT COUNT(*) FROM games WHERE workspace_id = $1::uuid) games,
                   (SELECT COUNT(*) FROM matches match
                    JOIN workspace_state state ON state.workspace_id=match.workspace_id
                                             AND state.active_analysis_run_id=match.analysis_run_id
                    WHERE match.workspace_id = $1::uuid) matched,
                   (SELECT COUNT(*) FROM matches match
                    JOIN workspace_state state ON state.workspace_id=match.workspace_id
                                             AND state.active_analysis_run_id=match.analysis_run_id
                    WHERE match.workspace_id = $1::uuid
                      AND match.compliance = 'FULLY_COMPLIANT') fully_compliant
            """, SETTINGS.workspace_id,
        )
    finally:
        await conn.close()
    return {key: int(values[key] or 0) for key in ("lines", "manual_priority", "auto_priority", "games", "matched", "fully_compliant")}


async def _stats_source() -> tuple[list[dict[str, Any]], dict[int, int | None], list[dict[str, Any]]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        games = await conn.fetch(
            """SELECT g.id, g.date, g.result, g.player_color, g.white_elo, g.black_elo,
                      m.matched_line_id AS line_id, m.deviation_ply_you, m.deviation_ply_opp, m.compliance
               FROM games g
               LEFT JOIN workspace_state ws ON ws.workspace_id=g.workspace_id
               LEFT JOIN matches m ON m.workspace_id=g.workspace_id AND m.game_id=g.id
                    AND m.analysis_run_id=ws.active_analysis_run_id
               WHERE g.workspace_id=$1::uuid""", SETTINGS.workspace_id,
        )
        evals = await conn.fetch(
            """SELECT ap.game_id, ap.post_eval_cp FROM analysis_ply ap
               JOIN workspace_state ws ON ws.workspace_id=ap.workspace_id AND ws.active_analysis_run_id=ap.analysis_run_id
               JOIN matches m ON m.workspace_id=ap.workspace_id AND m.game_id=ap.game_id
                             AND m.analysis_run_id=ws.active_analysis_run_id AND m.max_matched_ply=ap.ply
               WHERE ap.workspace_id=$1::uuid""", SETTINGS.workspace_id,
        )
        times = await conn.fetch(
            """SELECT gp.game_id, gp.time_spent_seconds, gp.time_spent_fraction, gp.is_self,
                      COALESCE(ap.repertoire_class, gp.repertoire_class) AS repertoire_class,
                      g.is_daily
               FROM game_positions gp JOIN games g ON g.workspace_id=gp.workspace_id AND g.id=gp.game_id
               LEFT JOIN workspace_state ws ON ws.workspace_id=gp.workspace_id
               LEFT JOIN analysis_ply ap ON ap.workspace_id=gp.workspace_id AND ap.game_id=gp.game_id
                                        AND ap.ply=gp.ply AND ap.analysis_run_id=ws.active_analysis_run_id
               WHERE gp.workspace_id=$1::uuid AND gp.time_spent_seconds IS NOT NULL""", SETTINGS.workspace_id,
        )
    finally:
        await conn.close()
    return [dict(row) for row in games], {int(row["game_id"]): row["post_eval_cp"] for row in evals}, [dict(row) for row in times]


def _outcome(game: dict[str, Any]) -> str | None:
    result, color = game.get("result"), game.get("player_color")
    if result == "1/2-1/2": return "draw"
    if result == "1-0": return "win" if color == "white" else "loss"
    if result == "0-1": return "win" if color == "black" else "loss"
    return None


def _aggregate(games: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    buckets: dict[Any, dict[str, Any]] = {}
    for game in games:
        key = key_fn(game)
        if key is None: continue
        row = buckets.setdefault(key, {"key": key, "total_games": 0, "fully_compliant": 0, "wins": 0, "losses": 0, "draws": 0})
        row["total_games"] += 1
        row["fully_compliant"] += int(game.get("compliance") == "FULLY_COMPLIANT")
        outcome = _outcome(game)
        if outcome: row[outcome + "s"] += 1
    for row in buckets.values():
        row["compliance_rate"] = row.pop("fully_compliant") / row["total_games"] if row["total_games"] else None
        row.update({"avg_deviation_ply": None, "avg_eval_exit": None, "in_book_avg": None, "out_book_avg": None,
                    "in_book_frac_avg": None, "out_book_frac_avg": None, "opp_dev_known_rate": None})
    return list(buckets.values())


async def fetch_lines_stats() -> list[dict[str, Any]]:
    games, _, _ = await _stats_source()
    rows = _aggregate(games, lambda game: game.get("line_id"))
    for row in rows: row["in_rep_other_rate"] = None
    return rows


async def fetch_line_stats_detail(line_id: str) -> dict[str, Any] | None:
    for row in await fetch_lines_stats():
        if str(row.get("key")) == line_id:
            return {**row, "line_id": line_id}
    return None


async def fetch_line_stats_history(line_id: str) -> dict[str, Any]:
    games, _, _ = await _stats_source()
    rows = _aggregate([game for game in games if game.get("line_id") == line_id], lambda game: str(game.get("date") or "Unknown")[:7])
    buckets = [{"bucket": row["key"], "total_games": row["total_games"]} for row in rows]
    return {"line_id": line_id, "buckets": sorted(buckets, key=lambda row: row["bucket"]), "totals": {"total_games": sum(row["total_games"] for row in buckets), "months": len(buckets)}}


async def fetch_time_usage_stats(pivot: str) -> dict[str, Any]:
    if pivot not in TIME_USAGE_PIVOTS: raise ValueError(f"Invalid time usage pivot: {pivot}")
    games, _, times = await _stats_source()
    names = ["Self", "Opponent"] if pivot == "self_vs_opp" else ["In book", "Out of book"]
    totals = {name: {"games": set(), "moves": 0, "seconds": 0.0} for name in names}
    for row in times:
        if row.get("is_daily"): continue
        if pivot == "self_vs_opp": name = "Self" if row.get("is_self") else "Opponent"
        else:
            if not row.get("is_self"): continue
            name = "In book" if row.get("repertoire_class") in {"IN_REPERTOIRE_MAIN", "IN_REPERTOIRE_OTHER"} else "Out of book"
        totals[name]["games"].add(int(row["game_id"])); totals[name]["moves"] += 1; totals[name]["seconds"] += float(row.get("time_spent_seconds") or 0)
    buckets = [{"bucket": name, "total_games": len(value["games"]), "total_moves": value["moves"],
                "avg_time_spent_seconds": value["seconds"] / value["moves"] if value["moves"] else None,
                "avg_time_spent_fraction": None} for name, value in totals.items()]
    return {"pivot": pivot, "buckets": buckets, "totals": {"total_games": len(games), "total_moves": sum(row["total_moves"] for row in buckets)}}


def _rating_band(value: Any, size: int) -> str:
    if value is None: return "Unknown"
    start = int(value) // size * size
    return f"{start}-{start + size - 1}"


async def fetch_rating_band_stats(band_size: int) -> list[dict[str, Any]]:
    games, _, _ = await _stats_source()
    rows = _aggregate(games, lambda game: (_rating_band(game.get("white_elo"), band_size), _rating_band(game.get("black_elo"), band_size)))
    for row in rows: row["white_band"], row["black_band"] = row.pop("key")
    return rows


async def fetch_rating_band_stats_payload(band_size: int) -> dict[str, Any]:
    size = normalize_rating_band_size(band_size); buckets = await fetch_rating_band_stats(size)
    rates = sorted(float(row["compliance_rate"]) for row in buckets if row.get("compliance_rate") is not None)
    percentile = lambda q: rates[int((len(rates) - 1) * q)] if rates else None
    return {"band_size": size, "allowed_band_sizes": ALLOWED_RATING_BAND_SIZES,
            "percentiles": {"p25_compliance_rate": percentile(.25), "p50_compliance_rate": percentile(.5), "p75_compliance_rate": percentile(.75)},
            "totals": {"total_games": sum(int(row["total_games"]) for row in buckets), "bucket_count": len(buckets)}, "buckets": buckets}


async def fetch_insights() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """SELECT insight.category, insight.title, insight.details, insight.data_json
               FROM insights insight
               JOIN workspace_state state ON state.workspace_id=insight.workspace_id
                                         AND state.active_analysis_run_id=insight.analysis_run_id
               WHERE insight.workspace_id=$1::uuid ORDER BY insight.created_at DESC""",
            SETTINGS.workspace_id,
        )
    finally: await conn.close()
    output = []
    for row in rows:
        data = dict(row); raw = data.pop("data_json", None)
        data["data"] = json.loads(raw) if isinstance(raw, str) else raw
        output.append(_normalize_insight_row(data))
    return _sort_insights(output)


async def fetch_review_items() -> list[dict[str, Any]]:
    conn = await asyncpg.connect(SETTINGS.postgres_dsn)
    try:
        rows = await conn.fetch(
            """SELECT item.line_id, item.reason, item.detail
               FROM review_items item
               JOIN workspace_state state ON state.workspace_id=item.workspace_id
                                         AND state.active_analysis_run_id=item.analysis_run_id
               WHERE item.workspace_id=$1::uuid ORDER BY item.reason, item.line_id""",
            SETTINGS.workspace_id,
        )
    finally: await conn.close()
    return [dict(row) for row in rows]
