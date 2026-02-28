from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from backend.settings import SETTINGS


def redis_client() -> Redis:
    return Redis.from_url(SETTINGS.redis_url, decode_responses=True)


async def ensure_consumer_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(
            name=SETTINGS.stream_name,
            groupname=SETTINGS.consumer_group,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue_job(redis: Redis, payload: dict[str, str]) -> str:
    return await redis.xadd(SETTINGS.stream_name, payload)


async def enqueue_dead_letter(redis: Redis, payload: dict[str, str]) -> str:
    return await redis.xadd(SETTINGS.dead_letter_stream, payload)
