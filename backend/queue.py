from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from backend.settings import SETTINGS

WORKLOAD_CLASSES = ("orchestration", "engine", "ingest")


def redis_client() -> Redis:
    return Redis.from_url(SETTINGS.redis_url, decode_responses=True)


async def ensure_consumer_group(redis: Redis, workload_class: str) -> None:
    if workload_class not in WORKLOAD_CLASSES:
        raise ValueError(f"Unsupported workload class: {workload_class}")
    try:
        await redis.xgroup_create(
            name=SETTINGS.stream_for(workload_class),
            groupname=SETTINGS.consumer_group_for(workload_class),
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def ensure_all_consumer_groups(redis: Redis) -> None:
    for workload_class in WORKLOAD_CLASSES:
        await ensure_consumer_group(redis, workload_class)


async def enqueue_job(redis: Redis, workload_class: str, payload: dict[str, str]) -> str:
    if workload_class not in WORKLOAD_CLASSES:
        raise ValueError(f"Unsupported workload class: {workload_class}")
    return await redis.xadd(SETTINGS.stream_for(workload_class), payload)


async def enqueue_dead_letter(redis: Redis, workload_class: str, payload: dict[str, str]) -> str:
    if workload_class not in WORKLOAD_CLASSES:
        raise ValueError(f"Unsupported workload class: {workload_class}")
    return await redis.xadd(SETTINGS.dead_letter_stream_for(workload_class), payload)
