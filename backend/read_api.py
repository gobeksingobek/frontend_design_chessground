from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from backend.settings import SETTINGS
from storage import queries


def _sqlite_backend_allowed() -> bool:
    return not SETTINGS.is_production_environment


def _raise_sqlite_disabled() -> None:
    raise RuntimeError(
        "SQLite backend is disabled in production. Set DATA_BACKEND=postgres and configure POSTGRES_DSN."
    )


def _fetch_games_sqlite(limit: int, offset: int) -> list[dict[str, Any]]:
    if not _sqlite_backend_allowed():
        _raise_sqlite_disabled()

    import sqlite3

    with sqlite3.connect(SETTINGS.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = queries.fetch_game_overview(conn)
    return rows[offset : offset + limit]


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
    }


async def _fetch_games_postgres(limit: int, offset: int) -> list[dict[str, Any]]:
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
            ORDER BY g.date DESC, g.id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(row) for row in rows]
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
        return {"header": header_data, "moves": [dict(row) for row in moves]}
    finally:
        await conn.close()


async def fetch_games(limit: int, offset: int) -> list[dict[str, Any]]:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_games_postgres(limit, offset)
    return await asyncio.to_thread(_fetch_games_sqlite, limit, offset)


async def fetch_game_detail(game_id: int) -> dict[str, Any] | None:
    if SETTINGS.data_backend == "postgres":
        return await _fetch_game_detail_postgres(game_id)
    return await asyncio.to_thread(_fetch_game_detail_sqlite, game_id)
