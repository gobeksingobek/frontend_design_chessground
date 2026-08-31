from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any, Literal

import asyncpg

from backend.settings import SETTINGS


WorkloadClass = Literal["orchestration", "engine", "ingest"]
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    return value


def record_to_job(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "job_id": str(record["id"]),
        "workspace_id": str(record["workspace_id"]),
        "parent_job_id": str(record["parent_job_id"]) if record.get("parent_job_id") else None,
        "job_type": str(record["job_type"]),
        "status": str(record["status"]),
        "priority": int(record["priority"]),
        "idempotency_key": str(record["idempotency_key"]),
        "request": _json_value(record["request_json"]) or {},
        "progress": _json_value(record["progress_json"]) or {},
        "result": _json_value(record["result_json"]) if record.get("result_json") is not None else None,
        "error_code": record.get("error_code"),
        "error_detail": record.get("error_detail"),
        "attempts": int(record["attempts"]),
        "max_attempts": int(record["max_attempts"]),
        "cancellation_requested": bool(record["cancellation_requested"]),
        "queued_at": record["queued_at"],
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "heartbeat_at": record.get("heartbeat_at"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def record_to_step(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "step_id": str(record["id"]),
        "job_id": str(record["job_id"]),
        "workspace_id": str(record["workspace_id"]),
        "workload_class": str(record["workload_class"]),
        "step_type": str(record["step_type"]),
        "status": str(record["status"]),
        "payload": _json_value(record["durable_payload"]) or {},
        "result": _json_value(record["result_json"]) if record.get("result_json") is not None else None,
        "deduplication_key": str(record["deduplication_key"]),
        "attempts": int(record["attempts"]),
        "max_attempts": int(record["max_attempts"]),
        "next_attempt_at": record.get("next_attempt_at"),
        "lease_owner": record.get("lease_owner"),
        "lease_expires_at": record.get("lease_expires_at"),
        "heartbeat_at": record.get("heartbeat_at"),
        "error_code": record.get("error_code"),
        "error_detail": record.get("error_detail"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


async def create_job(
    conn: asyncpg.Connection,
    *,
    job_type: str,
    workload_class: WorkloadClass,
    step_type: str,
    request_payload: dict[str, Any],
    idempotency_key: str,
    workspace_id: str = SETTINGS.workspace_id,
    priority: int = 0,
    max_attempts: int = SETTINGS.max_retries,
    parent_job_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Create one durable job and its initial step.

    Returns (job, step, created). Duplicate workspace/idempotency keys return the
    existing job and its first step without publishing a second message.
    """
    job_id = str(uuid.uuid4())
    step_id = str(uuid.uuid4())
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            INSERT INTO analysis_jobs(
                id, workspace_id, parent_job_id, job_type, status, priority,
                idempotency_key, request_json, max_attempts
            )
            VALUES($1::uuid, $2::uuid, $3::uuid, $4, 'queued', $5, $6, $7::jsonb, $8)
            ON CONFLICT (workspace_id, idempotency_key) DO NOTHING
            RETURNING *
            """,
            job_id,
            workspace_id,
            parent_job_id,
            job_type,
            priority,
            idempotency_key,
            json.dumps(request_payload),
            max_attempts,
        )
        created = row is not None
        if row is None:
            row = await conn.fetchrow(
                "SELECT * FROM analysis_jobs WHERE workspace_id = $1::uuid AND idempotency_key = $2",
                workspace_id,
                idempotency_key,
            )
            if row is None:
                raise RuntimeError("Idempotent job lookup failed after conflict.")
            step = await conn.fetchrow(
                "SELECT * FROM analysis_job_steps WHERE job_id = $1 ORDER BY created_at LIMIT 1",
                row["id"],
            )
            if step is None:
                raise RuntimeError("Existing job is missing its initial step.")
            return record_to_job(row), record_to_step(step), False

        step = await conn.fetchrow(
            """
            INSERT INTO analysis_job_steps(
                id, job_id, workspace_id, workload_class, step_type, status,
                durable_payload, deduplication_key, max_attempts
            )
            VALUES($1::uuid, $2::uuid, $3::uuid, $4, $5, 'queued', $6::jsonb, $7, $8)
            RETURNING *
            """,
            step_id,
            job_id,
            workspace_id,
            workload_class,
            step_type,
            json.dumps(request_payload),
            f"initial:{step_type}",
            max_attempts,
        )
    return record_to_job(row), record_to_step(step), True


async def add_step(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    workspace_id: str,
    workload_class: WorkloadClass,
    step_type: str,
    payload: dict[str, Any],
    deduplication_key: str,
    max_attempts: int = SETTINGS.max_retries,
) -> tuple[dict[str, Any], bool]:
    step_id = str(uuid.uuid4())
    row = await conn.fetchrow(
        """
        INSERT INTO analysis_job_steps(
            id, job_id, workspace_id, workload_class, step_type, status,
            durable_payload, deduplication_key, max_attempts
        )
        VALUES($1::uuid, $2::uuid, $3::uuid, $4, $5, 'queued', $6::jsonb, $7, $8)
        ON CONFLICT (job_id, deduplication_key) DO NOTHING
        RETURNING *
        """,
        step_id,
        job_id,
        workspace_id,
        workload_class,
        step_type,
        json.dumps(payload),
        deduplication_key,
        max_attempts,
    )
    if row is not None:
        return record_to_step(row), True
    row = await conn.fetchrow(
        "SELECT * FROM analysis_job_steps WHERE job_id = $1::uuid AND deduplication_key = $2",
        job_id,
        deduplication_key,
    )
    if row is None:
        raise RuntimeError("Idempotent step lookup failed after conflict.")
    return record_to_step(row), False


async def get_job(conn: asyncpg.Connection, job_id: str, workspace_id: str = SETTINGS.workspace_id) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT * FROM analysis_jobs WHERE id = $1::uuid AND workspace_id = $2::uuid",
        job_id,
        workspace_id,
    )
    return record_to_job(row) if row else None


async def list_jobs(
    conn: asyncpg.Connection,
    *,
    workspace_id: str = SETTINGS.workspace_id,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT * FROM analysis_jobs
        WHERE workspace_id = $1::uuid
          AND ($2::text IS NULL OR status = $2)
          AND ($3::text IS NULL OR job_type = $3)
        ORDER BY created_at DESC
        LIMIT $4
        """,
        workspace_id,
        status,
        job_type,
        min(max(limit, 1), 100),
    )
    return [record_to_job(row) for row in rows]


async def list_steps(conn: asyncpg.Connection, job_id: str, workspace_id: str = SETTINGS.workspace_id) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT * FROM analysis_job_steps
        WHERE job_id = $1::uuid AND workspace_id = $2::uuid
        ORDER BY created_at, id
        """,
        job_id,
        workspace_id,
    )
    return [record_to_step(row) for row in rows]


async def claim_step(
    conn: asyncpg.Connection,
    *,
    step_id: str,
    consumer_name: str,
    lease_seconds: int = SETTINGS.job_lease_seconds,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        UPDATE analysis_job_steps AS step
        SET status = 'running',
            attempts = attempts + 1,
            lease_owner = $2,
            lease_expires_at = NOW() + ($3 * INTERVAL '1 second'),
            heartbeat_at = NOW(),
            updated_at = NOW()
        FROM analysis_jobs AS job
        WHERE step.id = $1::uuid
          AND job.id = step.job_id
          AND (
              (step.status IN ('queued', 'retry')
               AND (step.next_attempt_at IS NULL OR step.next_attempt_at <= NOW()))
              OR
              (step.status = 'running' AND step.lease_expires_at < NOW())
          )
          AND job.status NOT IN ('completed', 'failed', 'cancelled')
          AND job.cancellation_requested = FALSE
        RETURNING step.*
        """,
        step_id,
        consumer_name,
        lease_seconds,
    )
    if row is None:
        return None
    await conn.execute(
        """
        UPDATE analysis_jobs
        SET status = 'running', started_at = COALESCE(started_at, NOW()),
            attempts = GREATEST(attempts, 1), heartbeat_at = NOW(), updated_at = NOW()
        WHERE id = $1
        """,
        row["job_id"],
    )
    return record_to_step(row)


async def heartbeat_step(conn: asyncpg.Connection, step_id: str, consumer_name: str) -> bool:
    result = await conn.execute(
        """
        UPDATE analysis_job_steps
        SET heartbeat_at = NOW(), lease_expires_at = NOW() + ($3 * INTERVAL '1 second'), updated_at = NOW()
        WHERE id = $1::uuid AND lease_owner = $2 AND status = 'running'
        """,
        step_id,
        consumer_name,
        SETTINGS.job_lease_seconds,
    )
    return result.endswith("1")


async def cancellation_requested(conn: asyncpg.Connection, job_id: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT cancellation_requested OR status = 'cancelled' FROM analysis_jobs WHERE id = $1::uuid",
            job_id,
        )
    )


async def cancel_running_step(conn: asyncpg.Connection, step_id: str) -> None:
    async with conn.transaction():
        job_id = await conn.fetchval(
            """
            UPDATE analysis_job_steps
            SET status='cancelled', lease_owner=NULL, lease_expires_at=NULL, updated_at=NOW()
            WHERE id=$1::uuid AND status='running'
            RETURNING job_id
            """,
            step_id,
        )
        if job_id is not None:
            await conn.execute(
                """
                UPDATE analysis_jobs SET status='cancelled', cancellation_requested=TRUE,
                    finished_at=NOW(), updated_at=NOW()
                WHERE id=$1::uuid
                """,
                job_id,
            )


async def _refresh_job_progress(conn: asyncpg.Connection, job_id: str) -> None:
    await conn.execute(
        """
        UPDATE analysis_jobs AS job
        SET progress_json = summary.payload,
            heartbeat_at = NOW(),
            updated_at = NOW()
        FROM (
            SELECT job_id,
                   jsonb_build_object(
                       'total', COUNT(*),
                       'queued', COUNT(*) FILTER (WHERE status IN ('queued', 'retry')),
                       'running', COUNT(*) FILTER (WHERE status = 'running'),
                       'completed', COUNT(*) FILTER (WHERE status = 'completed'),
                       'failed', COUNT(*) FILTER (WHERE status = 'failed'),
                       'cancelled', COUNT(*) FILTER (WHERE status = 'cancelled')
                   ) AS payload
            FROM analysis_job_steps
            WHERE job_id = $1::uuid
            GROUP BY job_id
        ) AS summary
        WHERE job.id = summary.job_id
        """,
        job_id,
    )


async def complete_step(conn: asyncpg.Connection, step_id: str, result: dict[str, Any]) -> str:
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE analysis_job_steps
            SET status = 'completed', result_json = $2::jsonb, error_code = NULL,
                error_detail = NULL, lease_owner = NULL, lease_expires_at = NULL,
                updated_at = NOW()
            WHERE id = $1::uuid AND status = 'running'
            RETURNING job_id
            """,
            step_id,
            json.dumps(result),
        )
        if row is None:
            raise RuntimeError(f"Step {step_id} is not running.")
        job_id = str(row["job_id"])
        await _refresh_job_progress(conn, job_id)
        if await conn.fetchval(
            "SELECT cancellation_requested FROM analysis_jobs WHERE id=$1::uuid", job_id
        ):
            await conn.execute(
                """
                UPDATE analysis_job_steps SET status='cancelled', updated_at=NOW()
                WHERE job_id=$1::uuid AND status IN ('queued', 'retry')
                """,
                job_id,
            )
            await conn.execute(
                """
                UPDATE analysis_jobs SET status='cancelled', finished_at=NOW(), updated_at=NOW()
                WHERE id=$1::uuid
                """,
                job_id,
            )
            return job_id
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM analysis_job_steps WHERE job_id = $1::uuid AND status NOT IN ('completed', 'cancelled')",
            job_id,
        )
        if int(remaining) == 0:
            from backend.analysis_results import finalize_analysis_run

            await finalize_analysis_run(conn, job_id)
            await conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'completed', result_json = $2::jsonb,
                    finished_at = NOW(), heartbeat_at = NOW(), updated_at = NOW()
                WHERE id = $1::uuid AND status NOT IN ('failed', 'cancelled')
                """,
                job_id,
                json.dumps(result),
            )
    return job_id


async def fail_step(
    conn: asyncpg.Connection,
    *,
    step_id: str,
    error_code: str,
    error_detail: str,
) -> tuple[str, str, int, str]:
    """Return (disposition, job_id, attempt, workload_class)."""
    async with conn.transaction():
        current = await conn.fetchrow("SELECT * FROM analysis_job_steps WHERE id = $1::uuid FOR UPDATE", step_id)
        if current is None:
            raise RuntimeError(f"Step {step_id} does not exist.")
        attempt = int(current["attempts"])
        max_attempts = int(current["max_attempts"])
        disposition = "failed" if attempt >= max_attempts else "retry"
        delay_seconds = min(300, 2 ** max(attempt - 1, 0))
        row = await conn.fetchrow(
            """
            UPDATE analysis_job_steps
            SET status = $2, error_code = $3, error_detail = $4,
                next_attempt_at = CASE WHEN $2 = 'retry' THEN NOW() + ($5 * INTERVAL '1 second') ELSE NULL END,
                lease_owner = NULL, lease_expires_at = NULL, updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING job_id, workload_class
            """,
            step_id,
            disposition,
            error_code,
            error_detail[:4000],
            delay_seconds,
        )
        job_id = str(row["job_id"])
        if disposition == "failed":
            await conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'failed', error_code = $2, error_detail = $3,
                    finished_at = NOW(), heartbeat_at = NOW(), updated_at = NOW()
                WHERE id = $1::uuid
                """,
                job_id,
                error_code,
                error_detail[:4000],
            )
        else:
            await conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'retry', error_code = $2, error_detail = $3,
                    heartbeat_at = NOW(), updated_at = NOW()
                WHERE id = $1::uuid
                """,
                job_id,
                error_code,
                error_detail[:4000],
            )
        await _refresh_job_progress(conn, job_id)
    return disposition, job_id, attempt, str(row["workload_class"])


async def cancel_job(conn: asyncpg.Connection, job_id: str, workspace_id: str = SETTINGS.workspace_id) -> dict[str, Any] | None:
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE analysis_jobs
            SET cancellation_requested = TRUE,
                status = CASE WHEN status IN ('queued', 'retry') THEN 'cancelled' ELSE status END,
                finished_at = CASE WHEN status IN ('queued', 'retry') THEN NOW() ELSE finished_at END,
                updated_at = NOW()
            WHERE id = $1::uuid AND workspace_id = $2::uuid
            RETURNING *
            """,
            job_id,
            workspace_id,
        )
        if row is None:
            return None
        await conn.execute(
            """
            UPDATE analysis_job_steps
            SET status = 'cancelled', updated_at = NOW()
            WHERE job_id = $1::uuid AND status IN ('queued', 'retry')
            """,
            job_id,
        )
    return record_to_job(row)


async def ready_dispatch_steps(
    conn: asyncpg.Connection,
    workload_class: WorkloadClass,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return durable work that may need (re)publishing.

    Retry rows become eligible at ``next_attempt_at``. Queued rows are also
    republished after a short grace period, closing the commit/publish gap if a
    producer exits after its PostgreSQL transaction but before ``XADD``.
    Duplicate stream deliveries remain harmless because claiming is conditional.
    """
    rows = await conn.fetch(
        """
        SELECT step.*
        FROM analysis_job_steps step
        JOIN analysis_jobs job ON job.id = step.job_id
        WHERE step.workload_class = $1
          AND (
              (step.status = 'retry' AND step.next_attempt_at <= NOW())
              OR (step.status = 'queued' AND step.updated_at <= NOW() - INTERVAL '10 seconds')
          )
          AND job.cancellation_requested = FALSE
          AND job.status NOT IN ('completed', 'failed', 'cancelled')
        ORDER BY COALESCE(step.next_attempt_at, step.updated_at), step.id
        LIMIT $2
        """,
        workload_class,
        min(max(limit, 1), 500),
    )
    return [record_to_step(row) for row in rows]


def redis_message(step: Mapping[str, Any], job_type: str) -> dict[str, str]:
    return {
        "schema_version": "1",
        "workspace_id": str(step["workspace_id"]),
        "job_id": str(step["job_id"]),
        "step_id": str(step["step_id"]),
        "job_type": job_type,
        "attempt": str(step.get("attempts", 0) + 1),
    }
