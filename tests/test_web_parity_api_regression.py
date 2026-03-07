from __future__ import annotations

import asyncio
import sys
import types

# FastAPI multipart import shim for test env.
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


def test_list_games_forwards_filters_and_sort(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_fetch_games(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(api_service, "fetch_games", fake_fetch_games)

    asyncio.run(
        api_service.list_games(
            limit=25,
            offset=5,
            result="1-0",
            compliance="FULLY_COMPLIANT",
            line_id="line-1",
            player="alpha",
            date_from="2024.01.01",
            date_to="2024.02.01",
            sort_by="compliance",
            sort_dir="asc",
            _="dev-user",
        )
    )

    assert len(calls) == 1
    assert calls[0]["limit"] == 25
    assert calls[0]["offset"] == 5
    assert calls[0]["sort_by"] == "compliance"
    assert calls[0]["sort_dir"] == "asc"
    assert calls[0]["line_id"] == "line-1"


def test_get_analysis_runs_uses_runtime_limit() -> None:
    manager = api_service.AnalysisRuntimeManager()
    manager._runs = [
        api_service.AnalysisRunHistoryEntry(
            job_id="j1",
            run_type="full-analysis",
            state="completed",
            started_at="2024-01-01T00:00:00+00:00",
            finished_at="2024-01-01T00:01:00+00:00",
            error=None,
        ),
        api_service.AnalysisRunHistoryEntry(
            job_id="j2",
            run_type="fetch-games",
            state="failed",
            started_at="2024-01-02T00:00:00+00:00",
            finished_at="2024-01-02T00:01:00+00:00",
            error="boom",
        ),
    ]

    result = manager.runs(limit=1)
    assert len(result.runs) == 1
    assert result.runs[0].job_id == "j1"
