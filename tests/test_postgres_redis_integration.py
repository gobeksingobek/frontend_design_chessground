from __future__ import annotations

import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from redis.asyncio import Redis

from backend import jobs
from backend.migrations import apply_pending_migrations, discover_migrations, migration_status


pytestmark = pytest.mark.integration


def test_upgrade_from_each_supported_migration_version() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 with PostgreSQL and Redis services.")

    async def scenario() -> None:
        source_dsn = os.environ["POSTGRES_DSN"]
        parsed = urlsplit(source_dsn)
        database_name = f"chessground_migration_{uuid.uuid4().hex}"
        target_dsn = urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))
        admin = await asyncpg.connect(source_dsn)
        try:
            await admin.execute(f'CREATE DATABASE "{database_name}"')
            target = await asyncpg.connect(target_dsn)
            try:
                migrations = discover_migrations()
                first = migrations[0]
                await target.execute(first.path.read_text(encoding="utf-8"))
                await target.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations(
                        version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                await target.execute(
                    "INSERT INTO schema_migrations(version, name, checksum) VALUES($1, $2, $3)",
                    first.version, first.name, first.checksum,
                )
                applied = await apply_pending_migrations(target)
                assert [migration.version for migration in applied] == [
                    migration.version for migration in migrations[1:]
                ]
                _, pending = await migration_status(target)
                assert pending == []
            finally:
                await target.close()
        finally:
            await admin.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            await admin.close()

    asyncio.run(scenario())


def test_durable_enqueue_claim_commit_ack_and_duplicate_delivery() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 with PostgreSQL and Redis services.")

    async def scenario() -> None:
        dsn = os.environ["POSTGRES_DSN"]
        redis_url = os.environ["REDIS_URL"]
        conn = await asyncpg.connect(dsn)
        redis = Redis.from_url(redis_url, decode_responses=True)
        stream = f"test:chessground:jobs:{uuid.uuid4()}"
        group = "test-workers"
        try:
            await apply_pending_migrations(conn)
            await redis.xgroup_create(stream, group, id="0", mkstream=True)
            idempotency_key = f"integration-{uuid.uuid4()}"
            job, step, created = await jobs.create_job(
                conn,
                job_type="integration-smoke",
                workload_class="engine",
                step_type="engine-position",
                request_payload={"fen": "test"},
                idempotency_key=idempotency_key,
            )
            assert created
            message_id = await redis.xadd(stream, jobs.redis_message(step, job["job_type"]))
            messages = await redis.xreadgroup(group, "consumer-a", {stream: ">"}, count=1)
            assert messages[0][1][0][0] == message_id
            claimed = await jobs.claim_step(conn, step_id=step["step_id"], consumer_name="consumer-a")
            assert claimed and claimed["status"] == "running"
            assert await jobs.claim_step(conn, step_id=step["step_id"], consumer_name="consumer-b") is None
            await jobs.complete_step(conn, step["step_id"], {"ok": True})
            assert await redis.xack(stream, group, message_id) == 1
            persisted = await jobs.get_job(conn, job["job_id"])
            assert persisted and persisted["status"] == "completed"

            duplicate_job, _, duplicate_created = await jobs.create_job(
                conn, job_type="integration-smoke", workload_class="engine",
                step_type="engine-position", request_payload={"fen": "test"},
                idempotency_key=idempotency_key,
            )
            assert not duplicate_created and duplicate_job["job_id"] == job["job_id"]

            reclaim_job, reclaim_step, _ = await jobs.create_job(
                conn, job_type="integration-reclaim", workload_class="engine",
                step_type="engine-position", request_payload={"fen": "reclaim"},
                idempotency_key=f"reclaim-{uuid.uuid4()}",
            )
            reclaim_message = await redis.xadd(stream, jobs.redis_message(reclaim_step, reclaim_job["job_type"]))
            await redis.xreadgroup(group, "consumer-a", {stream: ">"}, count=1)
            first_claim = await jobs.claim_step(
                conn, step_id=reclaim_step["step_id"], consumer_name="consumer-a", lease_seconds=1
            )
            assert first_claim and first_claim["attempts"] == 1
            await conn.execute(
                "UPDATE analysis_job_steps SET lease_expires_at=NOW()-INTERVAL '1 second' WHERE id=$1::uuid",
                reclaim_step["step_id"],
            )
            claimed_messages = await redis.xautoclaim(
                stream, group, "consumer-b", min_idle_time=0, start_id="0-0", count=10
            )
            assert any(message[0] == reclaim_message for message in claimed_messages[1])
            second_claim = await jobs.claim_step(
                conn, step_id=reclaim_step["step_id"], consumer_name="consumer-b"
            )
            assert second_claim and second_claim["attempts"] == 2
            await jobs.complete_step(conn, reclaim_step["step_id"], {"reclaimed": True})
            await redis.xack(stream, group, reclaim_message)

            cancel_job, cancel_step, _ = await jobs.create_job(
                conn, job_type="integration-cancel", workload_class="ingest",
                step_type="game-import", request_payload={},
                idempotency_key=f"cancel-{uuid.uuid4()}",
            )
            cancelled = await jobs.cancel_job(conn, cancel_job["job_id"])
            assert cancelled and cancelled["cancellation_requested"]
            assert await jobs.claim_step(
                conn, step_id=cancel_step["step_id"], consumer_name="consumer-a"
            ) is None

            other_workspace = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO workspaces(id, slug, name) VALUES($1::uuid, $2, 'Isolated')",
                other_workspace, f"isolated-{other_workspace}",
            )
            isolated_job, _, _ = await jobs.create_job(
                conn, job_type="integration-isolation", workload_class="ingest",
                step_type="game-import", request_payload={},
                idempotency_key=f"isolated-{uuid.uuid4()}", workspace_id=other_workspace,
            )
            assert await jobs.get_job(conn, isolated_job["job_id"]) is None
            assert await jobs.get_job(conn, isolated_job["job_id"], other_workspace) is not None
        finally:
            await redis.delete(stream)
            await redis.aclose()
            await conn.close()

    asyncio.run(scenario())
