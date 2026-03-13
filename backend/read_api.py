from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg

from backend.settings import SETTINGS
from analysis import statistics
from storage import queries


def _normalize_insight_row(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    refs = payload.get("source_refs") if isinstance(payload, dict) else None
    data["priority_score"] = float(payload.get("priority_score") or 0) if isinstance(payload, dict) else 0.0
    data["confidence"] = float(payload.get("confidence") or 0) if isinstance(payload, dict) else 0.0
    data["source_refs"] = refs if isinstance(refs, list) else []
    return data


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
        return sorted(rows, key=lambda row: (row.get("compliance") or "", row.get("date") or ""), reverse=reverse)
    if sort_by == "result":
        return sorted(rows, key=lambda row: (row.get("result") or "", row.get("date") or ""), reverse=reverse)
    return sorted(rows, key=lambda row: row.get("id") or 0, reverse=reverse)


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
            SELECT prev_game_id, next_game_id
            FROM (
                SELECT
                    id,
                    LAG(id) OVER (ORDER BY date DESC, id DESC) AS prev_game_id,
                    LEAD(id) OVER (ORDER BY date DESC, id DESC) AS next_game_id
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

    return {
        "header": header,
        "moves": enriched_moves,
        "prev_game_id": int(neighbors["prev_game_id"]) if neighbors and neighbors["prev_game_id"] is not None else None,
        "next_game_id": int(neighbors["next_game_id"]) if neighbors and neighbors["next_game_id"] is not None else None,
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
            SELECT prev_game_id, next_game_id
            FROM (
                SELECT
                    id,
                    LAG(id) OVER (ORDER BY date DESC, id DESC) AS prev_game_id,
                    LEAD(id) OVER (ORDER BY date DESC, id DESC) AS next_game_id
                FROM games
            ) ordered_games
            WHERE id = $1
            """,
            game_id,
        )
        return {
            "header": header_data,
            "moves": [dict(row) for row in moves],
            "prev_game_id": neighbors["prev_game_id"] if neighbors else None,
            "next_game_id": neighbors["next_game_id"] if neighbors else None,
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
            compliance_min=compliance_min,
            sort_by=sort_by,
            sort_dir=sort_dir,
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
        compliance_min=compliance_min,
        sort_by=sort_by,
        sort_dir=sort_dir,
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
    return sorted(results, key=lambda row: float(row.get("priority_score") or 0), reverse=True)


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
    return sorted(normalized, key=lambda row: float(row.get("priority_score") or 0), reverse=True)


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
    time_by_game = statistics.time_analysis.compute_time_usage_by_game(time_rows)
    stats: dict[str, dict[str, Any]] = {}
    for game in games:
        if pivot == "result":
            key = game.get("result") or "Unknown"
        elif pivot == "compliance":
            key = game.get("compliance") or "Unknown"
        else:
            date = game.get("date") or ""
            key = date[:7] if len(date) >= 7 else "Unknown"
        entry = stats.setdefault(str(key), statistics._init_stat_entry())
        statistics._accumulate_game(entry, game, eval_at_exit, time_by_game)
    return _normalize_time_usage_payload(statistics._finalize_stats(stats), pivot)


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
        return _build_time_usage_stats_payload([dict(row) for row in games], eval_at_exit, [dict(row) for row in time_rows], pivot)
    return await asyncio.to_thread(_fetch_time_usage_stats_sqlite, pivot)


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


async def fetch_insights() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_insights_postgres()
    return await asyncio.to_thread(_fetch_insights_sqlite)


async def fetch_review_items() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_review_items_postgres()
    return await asyncio.to_thread(_fetch_review_items_sqlite)
