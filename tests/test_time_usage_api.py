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


def test_time_usage_pivot_contract(monkeypatch) -> None:
    async def fake_stats(pivot: str):
        return {"pivot": pivot, "buckets": [{"bucket": pivot, "total_games": 3}], "totals": {"total_games": 3}}

    monkeypatch.setattr(api_service, "fetch_time_usage_stats", fake_stats)

    result = asyncio.run(api_service.get_time_usage_stats(pivot="result", _="dev-user"))

    assert result.pivot == "result"
    assert result.buckets[0]["bucket"] == "result"
    assert result.totals["total_games"] == 3
