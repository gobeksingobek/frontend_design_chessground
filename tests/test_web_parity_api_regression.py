from __future__ import annotations

import asyncio
import logging
import sys
import types

import pytest

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


def test_overview_summary_logs_backend_failure_without_rewriting_it(monkeypatch, caplog) -> None:
    failure = RuntimeError("operator does not exist: integer = boolean")

    async def fail_overview_summary():
        raise failure

    monkeypatch.setattr(api_service, "fetch_overview_summary", fail_overview_summary)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError) as exc_info:
        asyncio.run(api_service.get_overview_summary(_="dev-user"))

    assert exc_info.value is failure
    assert "Overview summary query failed" in caplog.text


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
