from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import asyncpg

from backend.settings import SETTINGS

REQUIRED_ANALYSIS_TABLES = (
    "positions",
    "games",
    "game_positions",
    "matches",
    "analysis_ply",
    "repertoire_lines",
    "repertoire_compact",
    "trainer_line_state",
    "trainer_sessions",
)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sideline_requests (
    id UUID PRIMARY KEY,
    game_id TEXT NOT NULL,
    move_ply INTEGER NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    result JSONB,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(SETTINGS.postgres_dsn, min_size=1, max_size=10)


async def ensure_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLE_SQL)


async def missing_tables(conn: asyncpg.Connection, table_names: tuple[str, ...]) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY($1::text[])
        """,
        list(table_names),
    )
    existing = {str(row["table_name"]) for row in rows}
    return [name for name in table_names if name not in existing]


async def ensure_analysis_schema_exists(pool: asyncpg.Pool) -> list[str]:
    async with pool.acquire() as conn:
        return await missing_tables(conn, REQUIRED_ANALYSIS_TABLES)


def _analysis_schema_sql_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "postgres" / "analysis_schema.sql"


async def apply_analysis_schema(conn: asyncpg.Connection) -> None:
    sql_path = _analysis_schema_sql_path()
    if not sql_path.exists():
        raise RuntimeError(f"Schema file not found: {sql_path}")
    await conn.execute(sql_path.read_text(encoding="utf-8"))


async def insert_sideline_request(
    conn: asyncpg.Connection,
    request_id: str,
    game_id: str,
    move_ply: int,
    requested_by: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        INSERT INTO sideline_requests(
            id, game_id, move_ply, requested_by, status, idempotency_key, payload
        ) VALUES($1::uuid, $2, $3, $4, 'queued', $5, $6::jsonb)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING *;
        """,
        request_id,
        game_id,
        move_ply,
        requested_by,
        idempotency_key,
        json.dumps(payload),
    )


async def fetch_by_idempotency_key(conn: asyncpg.Connection, idempotency_key: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM sideline_requests WHERE idempotency_key = $1", idempotency_key)


async def fetch_sideline_request(conn: asyncpg.Connection, request_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM sideline_requests WHERE id = $1::uuid", request_id)


async def list_sideline_requests(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch("SELECT * FROM sideline_requests ORDER BY created_at DESC LIMIT $1", limit)
