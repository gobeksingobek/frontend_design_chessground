from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from backend.settings import SETTINGS
from analysis import statistics
from storage import queries


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
        return queries.fetch_insights(conn)


def _fetch_review_items_sqlite() -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()
    import sqlite3
    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        return queries.fetch_review_items(conn)


async def fetch_overview_summary() -> dict[str, Any]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_overview_summary_sqlite)


async def fetch_lines_stats() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_lines_stats_sqlite)


async def fetch_time_usage_stats() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_time_usage_stats_sqlite)


async def fetch_rating_band_stats(band_size: int) -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_rating_band_stats_sqlite, band_size)


async def fetch_insights() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_insights_sqlite)


async def fetch_review_items() -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        _stats_not_supported_for_postgres()
    return await asyncio.to_thread(_fetch_review_items_sqlite)
