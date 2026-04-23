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


def test_lines_stats_detail_and_history_contract(monkeypatch) -> None:
    async def fake_detail(line_id: str):
        return {
            "line_id": line_id,
            "total_games": 2,
            "compliance_rate": 0.5,
            "in_rep_main_rate": 0.8,
            "in_rep_other_rate": 0.1,
            "out_of_rep_rate": 0.1,
        }

    async def fake_history(line_id: str):
        return {
            "line_id": line_id,
            "buckets": [
                {"bucket": "2024-01", "total_games": 1},
                {"bucket": "2024-02", "total_games": 1},
            ],
            "totals": {"total_games": 2, "months": 2},
        }

    monkeypatch.setattr(api_service, "fetch_line_stats_detail", fake_detail)
    monkeypatch.setattr(api_service, "fetch_line_stats_history", fake_history)

    detail = asyncio.run(api_service.get_line_stats_detail("line-a", _="dev-user"))
    history = asyncio.run(api_service.get_line_stats_history("line-a", _="dev-user"))

    assert detail["line_id"] == "line-a"
    assert {"line_id", "total_games", "compliance_rate", "in_rep_main_rate", "in_rep_other_rate", "out_of_rep_rate"}.issubset(detail.keys())
    assert history["line_id"] == "line-a"
    assert history["totals"]["total_games"] == 2
    assert history["totals"]["months"] == 2
    assert history["buckets"][0]["bucket"] == "2024-01"
    assert history["buckets"][1]["total_games"] == 1


def test_lines_stats_detail_not_found_raises(monkeypatch) -> None:
    async def fake_detail(_: str):
        return None

    monkeypatch.setattr(api_service, "fetch_line_stats_detail", fake_detail)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(api_service.get_line_stats_detail("missing-line", _="dev-user"))

    assert "Line stats not found" in str(exc_info.value)
