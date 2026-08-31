from __future__ import annotations

import threading
from typing import Any

import psycopg
from psycopg.rows import dict_row

from backend.settings import SETTINGS


class WorkerPostgresRepository:
    """Synchronous PostgreSQL repository used from worker compute threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection: psycopg.Connection | None = None

    def _conn(self) -> psycopg.Connection:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(SETTINGS.postgres_dsn, row_factory=dict_row)
        return self._connection

    def fetch_engine_cache(
        self,
        *,
        fen: str,
        depth: int,
        engine_id: str,
        mode: str,
        max_time_ms: int,
        options_hash: str,
    ) -> dict[str, Any] | None:
        with self._lock, self._conn().transaction():
            row = self._conn().execute(
                """
                SELECT cache.best_uci, cache.eval_cp
                FROM engine_cache cache
                JOIN positions position ON position.id=cache.pos_id
                WHERE position.fen_norm=%s AND cache.depth=%s AND cache.engine_id=%s
                  AND cache.mode=%s AND cache.max_time_ms=%s AND cache.options_hash=%s
                """,
                (fen, depth, engine_id, mode, max_time_ms, options_hash),
            ).fetchone()
        return dict(row) if row else None

    def persist_engine_cache(
        self,
        *,
        fen: str,
        depth: int,
        engine_id: str,
        mode: str,
        max_time_ms: int,
        options_hash: str,
        best_uci: str | None,
        eval_cp: int | None,
    ) -> None:
        with self._lock, self._conn().transaction():
            self._conn().execute(
                """
                INSERT INTO engine_cache(
                    pos_id, depth, engine_id, mode, max_time_ms, options_hash,
                    best_uci, eval_cp, analyzed_at
                )
                SELECT id, %s, %s, %s, %s, %s, %s, %s, NOW()
                FROM positions WHERE fen_norm=%s
                ON CONFLICT (pos_id, depth, engine_id, mode, max_time_ms, options_hash)
                DO UPDATE SET best_uci=EXCLUDED.best_uci, eval_cp=EXCLUDED.eval_cp,
                              analyzed_at=NOW()
                """,
                (depth, engine_id, mode, max_time_ms, options_hash, best_uci, eval_cp, fen),
            )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


WORKER_REPOSITORY = WorkerPostgresRepository()
