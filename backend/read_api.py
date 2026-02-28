from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

from backend.settings import SETTINGS
from storage import queries


def _connect_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(SETTINGS.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_games(limit: int, offset: int) -> list[dict[str, Any]]:
    with _connect_sqlite() as conn:
        rows = queries.fetch_game_overview(conn)
    return rows[offset : offset + limit]


def _fetch_game_detail(game_id: int) -> dict[str, Any] | None:
    with _connect_sqlite() as conn:
        header = queries.fetch_game_header(conn, game_id)
        if header is None:
            return None
        moves = queries.fetch_game_moves(conn, game_id)
    return {
        "header": header,
        "moves": moves,
    }


async def fetch_games(limit: int, offset: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_games, limit, offset)


async def fetch_game_detail(game_id: int) -> dict[str, Any] | None:
    return await asyncio.to_thread(_fetch_game_detail, game_id)
