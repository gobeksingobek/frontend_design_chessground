from __future__ import annotations

import asyncio
import sys
import types

import pytest

python_multipart_module = types.ModuleType("python_multipart")
python_multipart_module.__version__ = "0.0.20"
multipart_module = types.ModuleType("multipart")
multipart_module.__version__ = "0.0.20"
multipart_submodule = types.ModuleType("multipart.multipart")
multipart_submodule.parse_options_header = lambda value: (value, {})
multipart_module.multipart = multipart_submodule
sys.modules.setdefault("python_multipart", python_multipart_module)
sys.modules.setdefault("multipart", multipart_module)
sys.modules.setdefault("multipart.multipart", multipart_submodule)

from backend import api_service
from backend import read_api


def test_time_usage_pivot_contract(monkeypatch) -> None:
    async def fake_stats(pivot: str):
        return {"pivot": pivot, "buckets": [{"bucket": pivot, "total_games": 3}], "totals": {"total_games": 3}}

    monkeypatch.setattr(api_service, "fetch_time_usage_stats", fake_stats)

    result = asyncio.run(api_service.get_time_usage_stats(pivot="self_vs_opp", _="dev-user"))

    assert result.pivot == "self_vs_opp"
    assert result.buckets[0]["bucket"] == "self_vs_opp"
    assert result.totals["total_games"] == 3


def test_time_usage_supports_both_valid_pivots(monkeypatch) -> None:
    async def fake_stats(pivot: str):
        return {"pivot": pivot, "buckets": [{"bucket": pivot, "total_games": 1}], "totals": {"total_games": 1}}

    monkeypatch.setattr(api_service, "fetch_time_usage_stats", fake_stats)

    self_vs_opp = asyncio.run(api_service.get_time_usage_stats(pivot="self_vs_opp", _="dev-user"))
    in_book = asyncio.run(api_service.get_time_usage_stats(pivot="in_book_vs_out_of_book", _="dev-user"))

    assert self_vs_opp.pivot == "self_vs_opp"
    assert in_book.pivot == "in_book_vs_out_of_book"


def test_time_usage_rejects_invalid_pivot() -> None:
    with pytest.raises(ValueError, match="Invalid time usage pivot"):
        asyncio.run(read_api.fetch_time_usage_stats("invalid"))
