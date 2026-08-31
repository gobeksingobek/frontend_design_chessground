from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import asyncpg

from backend.settings import SETTINGS
from backend.migrations import require_current_schema

REQUIRED_ANALYSIS_TABLES = (
    "workspaces",
    "source_artifacts",
    "positions",
    "games",
    "game_positions",
    "matches",
    "analysis_ply",
    "repertoire_lines",
    "repertoire_compact",
    "trainer_line_state",
    "trainer_sessions",
    "analysis_jobs",
    "analysis_job_steps",
    "workspace_state",
)


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(SETTINGS.postgres_dsn, min_size=1, max_size=10)


async def ensure_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await require_current_schema(conn)


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


async def fetch_runtime_settings(pool: asyncpg.Pool) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payload FROM runtime_settings WHERE workspace_id = $1::uuid",
            SETTINGS.workspace_id,
        )
    return _decode_runtime_settings_payload(row["payload"]) if row is not None else None


def _decode_runtime_settings_payload(payload: Any) -> dict[str, Any]:
    """Normalize asyncpg JSONB results without depending on a pool-level codec."""
    if isinstance(payload, Mapping):
        return dict(payload)

    if isinstance(payload, (str, bytes, bytearray)):
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise RuntimeError("Persisted runtime settings contain invalid JSON.") from exc
        if isinstance(decoded, dict):
            return decoded

    raise RuntimeError("Persisted runtime settings must be a JSON object.")


async def save_runtime_settings(pool: asyncpg.Pool, payload: dict[str, Any]) -> dict[str, Any]:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO runtime_settings(workspace_id, payload, updated_at)
            VALUES ($1::uuid, $2::jsonb, NOW())
            ON CONFLICT (workspace_id) DO UPDATE
            SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            SETTINGS.workspace_id,
            json.dumps(payload),
        )
    return payload


async def insert_sideline_request(
    conn: asyncpg.Connection,
    request_id: str,
    game_id: str,
    move_ply: int,
    requested_by: str,
    job_id: str,
    payload: dict[str, Any],
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        INSERT INTO sideline_requests(
            id, workspace_id, job_id, game_id, move_ply, requested_by, payload
        ) VALUES($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb)
        ON CONFLICT (job_id) DO NOTHING
        RETURNING *;
        """,
        request_id,
        SETTINGS.workspace_id,
        job_id,
        game_id,
        move_ply,
        requested_by,
        json.dumps(payload),
    )


async def fetch_by_idempotency_key(conn: asyncpg.Connection, idempotency_key: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT request.*, job.status, job.result_json AS result, job.error_detail AS error,
               job.idempotency_key, job.attempts
        FROM sideline_requests request
        JOIN analysis_jobs job ON job.id = request.job_id
        WHERE job.workspace_id = $1::uuid AND job.idempotency_key = $2
        """,
        SETTINGS.workspace_id,
        idempotency_key,
    )


async def fetch_sideline_request(conn: asyncpg.Connection, request_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT request.*, job.status, job.result_json AS result, job.error_detail AS error,
               job.idempotency_key, job.attempts
        FROM sideline_requests request
        JOIN analysis_jobs job ON job.id = request.job_id
        WHERE request.id = $1::uuid AND request.workspace_id = $2::uuid
        """,
        request_id,
        SETTINGS.workspace_id,
    )


async def list_sideline_requests(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT request.*, job.status, job.result_json AS result, job.error_detail AS error,
               job.idempotency_key, job.attempts
        FROM sideline_requests request
        JOIN analysis_jobs job ON job.id = request.job_id
        WHERE request.workspace_id = $1::uuid
        ORDER BY request.created_at DESC LIMIT $2
        """,
        SETTINGS.workspace_id,
        limit,
    )
