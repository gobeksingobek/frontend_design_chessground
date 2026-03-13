from __future__ import annotations

import asyncio
import sys
import types

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
        return {"line_id": line_id, "total_games": 2}

    async def fake_history(line_id: str):
        return {"line_id": line_id, "buckets": [{"bucket": "2024-01", "total_games": 1}], "totals": {"total_games": 1, "months": 1}}

    monkeypatch.setattr(api_service, "fetch_line_stats_detail", fake_detail)
    monkeypatch.setattr(api_service, "fetch_line_stats_history", fake_history)

    detail = asyncio.run(api_service.get_line_stats_detail("line-a", _="dev-user"))
    history = asyncio.run(api_service.get_line_stats_history("line-a", _="dev-user"))

    assert detail["line_id"] == "line-a"
    assert {"line_id", "total_games"}.issubset(detail.keys())
    assert history["line_id"] == "line-a"
    assert {"buckets", "totals"}.issubset(history.keys())
