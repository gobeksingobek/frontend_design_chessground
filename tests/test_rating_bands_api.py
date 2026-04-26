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
from backend import read_api


def test_rating_band_guardrails_contract(monkeypatch) -> None:
    async def fake_rating_payload(_: int):
        return {
            "band_size": 100,
            "allowed_band_sizes": [50, 100, 150, 200, 250, 300, 350, 400],
            "percentiles": {"p25_compliance_rate": 0.4, "p50_compliance_rate": 0.5, "p75_compliance_rate": 0.8},
            "totals": {"total_games": 2, "bucket_count": 1},
            "buckets": [{"white_band": "1500-1599", "black_band": "1400-1499", "total_games": 2, "compliance_rate": 0.5}],
        }

    monkeypatch.setattr(api_service, "fetch_rating_band_stats_payload", fake_rating_payload)

    result = asyncio.run(api_service.get_rating_band_stats(band_size=125, _="dev-user"))

    assert result.band_size == 100
    assert 100 in result.allowed_band_sizes
    assert "p50_compliance_rate" in result.percentiles
    assert result.totals["total_games"] == 2
    assert len(result.buckets) == 1


def test_rating_band_guardrails_min_max_step(monkeypatch) -> None:
    captured_sizes: list[int] = []

    async def fake_payload(band_size: int):
        captured_sizes.append(band_size)
        return {
            "band_size": band_size,
            "allowed_band_sizes": [50, 100, 150, 200, 250, 300, 350, 400],
            "percentiles": {"p25_compliance_rate": None, "p50_compliance_rate": None, "p75_compliance_rate": None},
            "totals": {"total_games": 0, "bucket_count": 0},
            "buckets": [],
        }

    monkeypatch.setattr(api_service, "fetch_rating_band_stats_payload", fake_payload)

    below_min = asyncio.run(api_service.get_rating_band_stats(band_size=25, _="dev-user"))
    above_max = asyncio.run(api_service.get_rating_band_stats(band_size=450, _="dev-user"))
    bad_step = asyncio.run(api_service.get_rating_band_stats(band_size=125, _="dev-user"))
    good_step = asyncio.run(api_service.get_rating_band_stats(band_size=150, _="dev-user"))

    assert captured_sizes == [25, 450, 125, 150]
    assert below_min.band_size == 100
    assert above_max.band_size == 100
    assert bad_step.band_size == 100
    assert good_step.band_size == 150
    assert good_step.allowed_band_sizes == [50, 100, 150, 200, 250, 300, 350, 400]


def test_rating_band_payload_recomputes_when_band_size_changes(monkeypatch) -> None:
    captured_sizes: list[int] = []

    async def fake_fetch_stats(band_size: int):
        captured_sizes.append(band_size)
        if band_size == 100:
            return [
                {"white_band": "1500-1599", "black_band": "1400-1499", "total_games": 2, "compliance_rate": 0.25},
                {"white_band": "1600-1699", "black_band": "1500-1599", "total_games": 3, "compliance_rate": 0.75},
            ]
        return [
            {"white_band": "1400-1599", "black_band": "1400-1599", "total_games": 5, "compliance_rate": 0.5},
        ]

    monkeypatch.setattr(read_api, "fetch_rating_band_stats", fake_fetch_stats)

    payload_100 = asyncio.run(read_api.fetch_rating_band_stats_payload(100))
    payload_200 = asyncio.run(read_api.fetch_rating_band_stats_payload(200))

    assert captured_sizes == [100, 200]
    assert payload_100["band_size"] == 100
    assert payload_200["band_size"] == 200
    assert payload_100["totals"] == {"total_games": 5, "bucket_count": 2}
    assert payload_200["totals"] == {"total_games": 5, "bucket_count": 1}
    assert payload_100["percentiles"]["p50_compliance_rate"] == 0.25
    assert payload_200["percentiles"]["p50_compliance_rate"] == 0.5
    assert payload_100["allowed_band_sizes"] == read_api.ALLOWED_RATING_BAND_SIZES
    assert payload_200["allowed_band_sizes"] == read_api.ALLOWED_RATING_BAND_SIZES
