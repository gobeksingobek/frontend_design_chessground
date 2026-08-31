from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from backend import api_service


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Acquire:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    async def __aenter__(self) -> object:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


def _request(connection: object) -> Any:
    pool = SimpleNamespace(acquire=lambda: _Acquire(connection))
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))


class _PositionConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object) -> dict[str, object]:
        self.calls.append((query, args))
        if "FROM positions" in query:
            return {"pos_id": 7, "fen": "fen", "side_to_move": "w"}
        return {}

    async def fetchval(self, _query: str, *_args: object) -> bool:
        return False

    async def fetch(self, _query: str, *_args: object) -> list[dict[str, object]]:
        return []


def test_position_lookup_supplies_only_declared_postgres_parameters() -> None:
    connection = _PositionConnection()
    payload = asyncio.run(
        api_service._fetch_position_intelligence_summary_backend(
            7, _request(connection), limit=8
        )
    )

    position_query, position_args = connection.calls[0]
    assert "WHERE id = $1" in position_query
    assert position_args == (7,)
    assert payload["position"]["pos_id"] == 7


class _ReviewConnection:
    def __init__(self) -> None:
        self.temporal_bindings: list[object] = []
        self.now = datetime.now(timezone.utc)

    def transaction(self) -> _Transaction:
        return _Transaction()

    async def fetchrow(self, query: str, *_args: object) -> dict[str, object] | None:
        if "SELECT id, status, evidence_count, line_id_hint" in query:
            return {"id": 101, "status": "PENDING", "evidence_count": 7, "line_id_hint": None}
        if "proposition_key" in query:
            return {
                "id": 101,
                "proposition_type": "MISSING_COVERAGE_BRANCH",
                "proposition_key": "p-101",
                "status": "APPROVED",
                "evidence_count": 7,
                "threshold_count": 5,
                "dismissed_count": 0,
                "pos_id": 1,
                "uci_move": "e2e4",
                "line_id_hint": None,
                "detail_json": {},
                "created_at": self.now,
                "updated_at": self.now,
                "decided_at": self.now,
            }
        return None

    async def execute(self, query: str, *args: object) -> str:
        if "decided_at" in query or "queued_at" in query:
            self.temporal_bindings.append(args[1])
        return "UPDATE 1" if query.lstrip().startswith("UPDATE") else "INSERT 0 1"


def test_review_mutations_bind_datetimes_and_response_accepts_them() -> None:
    connection = _ReviewConnection()
    result = asyncio.run(
        api_service._execute_review_action_backend(101, "done", _request(connection))
    )

    assert connection.temporal_bindings
    assert all(isinstance(value, datetime) for value in connection.temporal_bindings)
    response = api_service.ReviewPropositionDetailResponse(**result["proposition"])
    assert response.status == "APPROVED"
    assert response.updated_at.tzinfo is not None
