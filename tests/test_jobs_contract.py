from __future__ import annotations

from backend.jobs import redis_message
from backend.settings import SETTINGS


def test_redis_message_is_pointer_only() -> None:
    step = {
        "workspace_id": SETTINGS.workspace_id,
        "job_id": "00000000-0000-0000-0000-000000000010",
        "step_id": "00000000-0000-0000-0000-000000000011",
        "attempts": 2,
        "payload": {"fen": "must-not-leak"},
    }
    message = redis_message(step, "engine-position")
    assert message == {
        "schema_version": "1",
        "workspace_id": SETTINGS.workspace_id,
        "job_id": step["job_id"],
        "step_id": step["step_id"],
        "job_type": "engine-position",
        "attempt": "3",
    }


def test_capability_stream_names_are_fixed() -> None:
    assert SETTINGS.stream_for("orchestration") == "chessground:jobs:orchestration"
    assert SETTINGS.stream_for("engine") == "chessground:jobs:engine"
    assert SETTINGS.stream_for("ingest") == "chessground:jobs:ingest"
    assert SETTINGS.dead_letter_stream_for("engine") == "chessground:jobs:engine:dead"
