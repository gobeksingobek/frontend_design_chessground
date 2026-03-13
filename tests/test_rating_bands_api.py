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


def test_rating_band_guardrails_contract(monkeypatch) -> None:
    async def fake_rating_stats(band_size: int):
        return [{"white_band": "1500-1599", "black_band": "1400-1499", "total_games": 2, "compliance_rate": 0.5}]

    monkeypatch.setattr(api_service, "fetch_rating_band_stats", fake_rating_stats)

    result = asyncio.run(api_service.get_rating_band_stats(band_size=125, _="dev-user"))

    assert result.band_size == 100
    assert 100 in result.allowed_band_sizes
    assert "p50_compliance_rate" in result.percentiles
    assert result.totals["total_games"] == 2
    assert len(result.buckets) == 1
