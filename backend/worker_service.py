from __future__ import annotations

import argparse
import asyncio
import logging
import threading
from typing import Any

import asyncpg
import chess
import chess.engine

from backend import db, jobs
from backend.queue import enqueue_dead_letter, enqueue_job, ensure_consumer_group, redis_client
from backend.settings import SETTINGS
from backend.worker_repository import WORKER_REPOSITORY


LOGGER = logging.getLogger("chessground.worker")
_ENGINE_LOCK = threading.Lock()
_ENGINE: chess.engine.SimpleEngine | None = None


def _engine() -> chess.engine.SimpleEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = chess.engine.SimpleEngine.popen_uci(SETTINGS.stockfish_path)
    return _ENGINE


def close_engine() -> None:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            try:
                _ENGINE.quit()
            finally:
                _ENGINE = None


async def _heartbeat_loop(pool: asyncpg.Pool, step_id: str) -> None:
    interval = max(1, SETTINGS.job_lease_seconds // 3)
    while True:
        await asyncio.sleep(interval)
        async with pool.acquire() as heartbeat_conn:
            if not await jobs.heartbeat_step(heartbeat_conn, step_id, SETTINGS.consumer_name):
                return


def run_stockfish_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Run canonical server-side Stockfish evaluation for a bounded branch."""
    board = chess.Board(payload["fen"])
    branch_moves = payload.get("branch_moves") or []
    analysis: list[dict[str, Any]] = []
    with _ENGINE_LOCK:
        engine = _engine()
        for uci in branch_moves:
            move = chess.Move.from_uci(str(uci))
            if move not in board.legal_moves:
                raise ValueError(f"Illegal move in branch: {uci}")
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(depth=SETTINGS.stockfish_depth))
            score = info["score"].white().score(mate_score=100000)
            analysis.append({"move": str(uci), "score_cp": score})
    result: dict[str, Any] = {
        "start_fen": payload["fen"],
        "branch_analysis": analysis,
        "depth": SETTINGS.stockfish_depth,
        "engine_id": SETTINGS.stockfish_engine_id,
        "canonical": True,
    }
    if payload.get("eval_metadata") is not None:
        result["advisory_eval"] = payload["eval_metadata"]
    return result


def run_position_analysis(fen: str, depth: int) -> tuple[int | None, str | None]:
    board = chess.Board(fen)
    with _ENGINE_LOCK:
        info = _engine().analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].white().score(mate_score=100000)
    best_move = info.get("pv", [None])[0]
    return score, best_move.uci() if best_move else None


async def _execute_engine_step(conn: asyncpg.Connection, step: dict[str, Any]) -> dict[str, Any]:
    if step["step_type"] == "sideline-analysis":
        return await asyncio.to_thread(run_stockfish_analysis, step["payload"])
    if step["step_type"] != "engine-position":
        raise ValueError(f"Unsupported engine step: {step['step_type']}")

    payload = step["payload"]
    fen = str(payload["fen"])
    depth = int(payload.get("depth") or SETTINGS.stockfish_depth)
    engine_id = str(payload.get("engine_id") or SETTINGS.stockfish_engine_id)
    mode = str(payload.get("mode") or "fixed")
    max_time_ms = int(payload.get("max_time_ms") or 0)
    options_hash = str(payload.get("options_hash") or "")
    cached = await asyncio.to_thread(
        WORKER_REPOSITORY.fetch_engine_cache,
        fen=fen,
        depth=depth,
        engine_id=engine_id,
        mode=mode,
        max_time_ms=max_time_ms,
        options_hash=options_hash,
    )
    if cached is not None:
        return {
            "fen": fen,
            "depth": depth,
            "engine_id": engine_id,
            "score_cp": cached["eval_cp"],
            "best_uci": cached["best_uci"],
            "cache_hit": True,
            "canonical": True,
        }
    started = asyncio.get_running_loop().time()
    score, best_uci = await asyncio.to_thread(run_position_analysis, fen, depth)
    duration_ms = round((asyncio.get_running_loop().time() - started) * 1000)
    result = {
        "fen": fen,
        "depth": depth,
        "engine_id": engine_id,
        "score_cp": score,
        "best_uci": best_uci,
        "duration_ms": duration_ms,
        "canonical": True,
        "cache_hit": False,
    }
    await asyncio.to_thread(
        WORKER_REPOSITORY.persist_engine_cache,
        fen=fen,
        depth=depth,
        engine_id=engine_id,
        mode=mode,
        max_time_ms=max_time_ms,
        options_hash=options_hash,
        best_uci=result["best_uci"],
        eval_cp=score,
    )
    return result


async def execute_step(conn: asyncpg.Connection, redis, capability: str, step: dict[str, Any]) -> dict[str, Any]:
    if capability == "engine":
        return await _execute_engine_step(conn, step)
    if capability == "ingest":
        from backend.ingest_workflows import execute_ingest_step
        locked = await conn.fetchval(
            "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
            step["workspace_id"],
        )
        if not locked:
            raise RuntimeError("A conflicting workspace ingest or analysis job is active.")
        try:
            return await execute_ingest_step(conn, step)
        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
                step["workspace_id"],
            )
    if capability == "orchestration":
        from backend.orchestration import execute_orchestration_step

        return await execute_orchestration_step(conn, redis, step)
    raise ValueError(f"Unsupported worker capability: {capability}")


async def process_message(
    pool: asyncpg.Pool,
    redis,
    capability: str,
    message_id: str,
    values: dict[str, str],
) -> None:
    stream = SETTINGS.stream_for(capability)
    group = SETTINGS.consumer_group_for(capability)
    step_id = values.get("step_id")
    if not step_id:
        await enqueue_dead_letter(redis, capability, {**values, "error": "missing step_id"})
        await redis.xack(stream, group, message_id)
        return

    async with pool.acquire() as conn:
        step = await jobs.claim_step(conn, step_id=step_id, consumer_name=SETTINGS.consumer_name)
        if step is None:
            await redis.xack(stream, group, message_id)
            return
        heartbeat_task = asyncio.create_task(_heartbeat_loop(pool, step_id))
        durable_disposition_committed = False
        try:
            if await jobs.cancellation_requested(conn, step["job_id"]):
                await jobs.cancel_running_step(conn, step_id)
                durable_disposition_committed = True
                return
            result = await execute_step(conn, redis, capability, step)
            await jobs.complete_step(conn, step_id, result)
            durable_disposition_committed = True
            if capability == "engine":
                LOGGER.info(
                    "engine result workspace=%s job=%s step=%s profile=%s cache=%s duration_ms=%s disposition=committed",
                    step["workspace_id"], step["job_id"], step_id,
                    result.get("engine_id"),
                    "hit" if result.get("cache_hit") else "miss",
                    result.get("duration_ms"),
                )
            LOGGER.info(
                "step completed workspace=%s job=%s step=%s type=%s attempt=%s",
                step["workspace_id"], step["job_id"], step_id, step["step_type"], step["attempts"],
            )
        except Exception as exc:  # noqa: BLE001
            disposition, job_id, attempt, workload_class = await jobs.fail_step(
                conn,
                step_id=step_id,
                error_code=type(exc).__name__.upper(),
                error_detail=str(exc),
            )
            LOGGER.exception(
                "step failed workspace=%s job=%s step=%s disposition=%s",
                step["workspace_id"], job_id, step_id, disposition,
            )
            if disposition == "failed":
                await enqueue_dead_letter(
                    redis,
                    workload_class,
                    {
                        **jobs.redis_message(step, values.get("job_type", step["step_type"])),
                        "attempt": str(attempt),
                        "error": str(exc)[:1000],
                    },
                )
            durable_disposition_committed = True
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            # Leave the entry pending when execution is interrupted before a
            # durable completion/retry/cancellation transaction commits. Its
            # lease then expires and XAUTOCLAIM can safely deliver it again.
            if durable_disposition_committed:
                await redis.xack(stream, group, message_id)


async def dispatch_durable_work(pool: asyncpg.Pool, redis, capability: str) -> int:
    async with pool.acquire() as conn:
        steps = await jobs.ready_dispatch_steps(conn, capability)
        published = 0
        for step in steps:
            job = await jobs.get_job(conn, step["job_id"], step["workspace_id"])
            if job is None:
                continue
            await enqueue_job(redis, step["workload_class"], jobs.redis_message(step, job["job_type"]))
            published += 1
        return published


async def _claim_abandoned(redis, capability: str) -> list[tuple[str, dict[str, str]]]:
    stream = SETTINGS.stream_for(capability)
    group = SETTINGS.consumer_group_for(capability)
    response = await redis.xautoclaim(
        stream,
        group,
        SETTINGS.consumer_name,
        min_idle_time=SETTINGS.pending_claim_idle_ms,
        start_id="0-0",
        count=10,
    )
    return list(response[1]) if len(response) > 1 else []


async def run_worker(capability: str | None = None) -> None:
    selected = capability or SETTINGS.worker_capability
    if selected not in {"orchestration", "engine", "ingest"}:
        raise ValueError("Worker capability must be orchestration, engine, or ingest.")
    SETTINGS.validate_deployment_config(selected)
    pool = await db.create_pool()
    await db.ensure_schema(pool)
    redis = redis_client()
    await ensure_consumer_group(redis, selected)
    stream = SETTINGS.stream_for(selected)
    group = SETTINGS.consumer_group_for(selected)
    try:
        while True:
            for message_id, values in await _claim_abandoned(redis, selected):
                await process_message(pool, redis, selected, message_id, values)
            await dispatch_durable_work(pool, redis, selected)
            streams = await redis.xreadgroup(
                groupname=group,
                consumername=SETTINGS.consumer_name,
                streams={stream: ">"},
                count=10,
                block=SETTINGS.stream_block_ms,
            )
            for _, messages in streams or []:
                for message_id, values in messages:
                    await process_message(pool, redis, selected, message_id, values)
    finally:
        if selected == "engine":
            await asyncio.to_thread(close_engine)
            await asyncio.to_thread(WORKER_REPOSITORY.close)
        await redis.aclose()
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one capability-specific ChessGround worker.")
    parser.add_argument(
        "--capability",
        choices=("orchestration", "engine", "ingest"),
        default=SETTINGS.worker_capability,
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker(args.capability))


if __name__ == "__main__":
    main()
