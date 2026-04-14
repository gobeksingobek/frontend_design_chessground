from __future__ import annotations

import asyncio

import pytest

from backend import read_api


def test_time_usage_stats_accepts_supported_pivots(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_connect(_dsn: str):  # pragma: no cover - postgres path not used
        raise AssertionError("postgres should not be used in this unit test")

    monkeypatch.setattr(read_api, "SETTINGS", type("S", (), {"data_backend": "sqlite"})())
    monkeypatch.setattr(read_api, "_fetch_time_usage_stats_sqlite", lambda pivot: {"pivot": pivot, "buckets": [], "totals": {}})
    monkeypatch.setattr(read_api.asyncpg, "connect", fake_connect)

    assert asyncio.run(read_api.fetch_time_usage_stats("self_vs_opp"))["pivot"] == "self_vs_opp"
    assert (
        asyncio.run(read_api.fetch_time_usage_stats("in_book_vs_out_of_book"))["pivot"]
        == "in_book_vs_out_of_book"
    )


def test_time_usage_stats_rejects_invalid_pivot() -> None:
    with pytest.raises(ValueError, match="Invalid time usage pivot"):
        read_api._build_time_usage_stats_payload([], {}, [], "month")
