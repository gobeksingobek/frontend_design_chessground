from __future__ import annotations

import asyncio

import pytest

from backend import jobs, worker_service


class _Acquire:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Pool:
    def acquire(self) -> _Acquire:
        return _Acquire()


class _Redis:
    def __init__(self) -> None:
        self.acknowledged: list[tuple[str, str, str]] = []

    async def xack(self, stream: str, group: str, message_id: str) -> None:
        self.acknowledged.append((stream, group, message_id))


def test_interrupted_step_remains_pending_for_xautoclaim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = {
        "step_id": "00000000-0000-0000-0000-000000000011",
        "job_id": "00000000-0000-0000-0000-000000000010",
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "step_type": "engine-position",
        "attempts": 1,
    }

    async def claim_step(*_args: object, **_kwargs: object) -> dict[str, object]:
        return step

    async def not_cancelled(*_args: object, **_kwargs: object) -> bool:
        return False

    async def interrupt(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise asyncio.CancelledError

    monkeypatch.setattr(jobs, "claim_step", claim_step)
    monkeypatch.setattr(jobs, "cancellation_requested", not_cancelled)
    monkeypatch.setattr(worker_service, "execute_step", interrupt)
    redis = _Redis()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            worker_service.process_message(
                _Pool(),
                redis,
                "engine",
                "1-0",
                {"step_id": str(step["step_id"]), "job_type": "engine-position"},
            )
        )

    assert redis.acknowledged == []
