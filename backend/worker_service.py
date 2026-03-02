from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import chess
import chess.engine

from backend import db
from backend.queue import enqueue_dead_letter, enqueue_job, ensure_consumer_group, redis_client
from backend.settings import SETTINGS


async def claim_job(conn: asyncpg.Connection, job_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        UPDATE sideline_requests
        SET status = 'processing', updated_at = NOW()
        WHERE id = $1::uuid AND status IN ('queued', 'retry')
        RETURNING *;
        """,
        job_id,
    )


async def mark_complete(conn: asyncpg.Connection, job_id: str, result: dict[str, Any]) -> None:
    await conn.execute(
        """
        UPDATE sideline_requests
        SET status = 'completed', result = $2::jsonb, error = NULL, updated_at = NOW()
        WHERE id = $1::uuid;
        """,
        job_id,
        json.dumps(result),
    )


async def mark_retry_or_failure(conn: asyncpg.Connection, job_id: str, error: str, attempt: int) -> str:
    if attempt >= SETTINGS.max_retries:
        await conn.execute(
            """
            UPDATE sideline_requests
            SET status = 'failed', error = $2, attempts = $3, updated_at = NOW()
            WHERE id = $1::uuid;
            """,
            job_id,
            error,
            attempt,
        )
        return "failed"

    await conn.execute(
        """
        UPDATE sideline_requests
        SET status = 'retry', error = $2, attempts = $3, updated_at = NOW()
        WHERE id = $1::uuid;
        """,
        job_id,
        error,
        attempt,
    )
    return "retry"


def run_stockfish_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    board = chess.Board(payload["fen"])
    branch_moves = payload["branch_moves"]
    analysis: list[dict[str, Any]] = []

    with chess.engine.SimpleEngine.popen_uci(SETTINGS.stockfish_path) as engine:
        for uci in branch_moves:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(f"Illegal move in branch: {uci}")
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(depth=SETTINGS.stockfish_depth))
            score = info["score"].pov(board.turn).score(mate_score=100000)
            analysis.append({"move": uci, "score_cp": score})

    result: dict[str, Any] = {
        "start_fen": payload["fen"],
        "branch_analysis": analysis,
        "depth": SETTINGS.stockfish_depth,
    }
    if payload.get("eval_metadata") is not None:
        result["advisory_eval"] = payload["eval_metadata"]
    return result


async def process_message(pool: asyncpg.Pool, redis, message_id: str, values: dict[str, str]) -> None:
    job_id = values["job_id"]
    attempt = int(values.get("attempt", "0")) + 1

    async with pool.acquire() as conn:
        request_row = await claim_job(conn, job_id)
        if request_row is None:
            await redis.xack(SETTINGS.stream_name, SETTINGS.consumer_group, message_id)
            return

        payload = request_row["payload"]
        try:
            result = run_stockfish_analysis(payload)
            await mark_complete(conn, job_id, result)
            await redis.xack(SETTINGS.stream_name, SETTINGS.consumer_group, message_id)
        except Exception as exc:  # noqa: BLE001
            disposition = await mark_retry_or_failure(conn, job_id, str(exc), attempt)
            if disposition == "retry":
                await enqueue_job(
                    redis,
                    {
                        "job_id": job_id,
                        "idempotency_key": request_row["idempotency_key"],
                        "attempt": str(attempt),
                    },
                )
            else:
                await enqueue_dead_letter(
                    redis,
                    {
                        "job_id": job_id,
                        "idempotency_key": request_row["idempotency_key"],
                        "attempt": str(attempt),
                        "error": str(exc),
                    },
                )
            await redis.xack(SETTINGS.stream_name, SETTINGS.consumer_group, message_id)


async def run_worker() -> None:
    pool = await db.create_pool()
    await db.ensure_schema(pool)

    redis = redis_client()
    await ensure_consumer_group(redis)

    try:
        while True:
            streams = await redis.xreadgroup(
                groupname=SETTINGS.consumer_group,
                consumername=SETTINGS.consumer_name,
                streams={SETTINGS.stream_name: ">"},
                count=10,
                block=SETTINGS.stream_block_ms,
            )
            if not streams:
                continue

            for _, messages in streams:
                for message_id, values in messages:
                    await process_message(pool, redis, message_id, values)
    finally:
        await redis.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
