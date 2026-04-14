from __future__ import annotations

import asyncio
import sys
import types

from fastapi import HTTPException

# FastAPI validates multipart support at import time for UploadFile routes.
# Provide a tiny stub so these endpoint tests can import api_service in environments
# where python-multipart is not preinstalled.
python_multipart_module = types.ModuleType("python_multipart")
python_multipart_module.__version__ = "0.0.20"

multipart_module = types.ModuleType("multipart")
multipart_module.__version__ = "0.0.20"
multipart_submodule = types.ModuleType("multipart.multipart")


def _parse_options_header(value: str):
    return value, {}


multipart_submodule.parse_options_header = _parse_options_header
multipart_module.multipart = multipart_submodule
sys.modules.setdefault("python_multipart", python_multipart_module)
sys.modules.setdefault("multipart", multipart_module)
sys.modules.setdefault("multipart.multipart", multipart_submodule)

from backend import api_service


# Canonical traversal contract is GET /games/{id} neighbor fields;
# any dedicated /games/{id}/neighbors route is compatibility-only during migration.

def test_list_games_bounds_limit_and_offset(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    async def fake_fetch_games(**kwargs):
        calls.append((kwargs["limit"], kwargs["offset"]))
        return [
            {
                "id": 11,
                "date": "2024.01.01",
                "white": "Alpha",
                "black": "Beta",
                "result": "1-0",
                "time_control": "600+5",
                "white_elo": 1800,
                "black_elo": 1750,
                "line_id": "line-1",
                "compliance": "FULLY_COMPLIANT",
                "max_matched_ply": 16,
                "matching_mode": "strict",
                "who_left_first": "opponent",
                "in_main": 10,
                "in_other": 3,
                "out_rep": 1,
            }
        ]

    monkeypatch.setattr(api_service, "fetch_games", fake_fetch_games)

    result = asyncio.run(api_service.list_games(limit=999, offset=-5, _="dev-user"))

    assert calls == [(200, 0)]
    assert len(result) == 1
    assert result[0].id == 11


def test_get_game_returns_payload_from_read_layer(monkeypatch) -> None:
    async def fake_fetch_game_detail(game_id: int):
        assert game_id == 44
        return {
            "header": {"id": 44, "result": "0-1"},
            "moves": [
                {
                    "ply": 1,
                    "pos_id": 1,
                    "fen": "startpos",
                    "san_move": "e4",
                    "uci_move": "e2e4",
                    "repertoire_class": "IN_REPERTOIRE_MAIN",
                    "is_self": 1,
                    "clock_seconds": 590.0,
                    "time_spent_seconds": 10.0,
                    "time_spent_fraction": 0.02,
                    "pre_eval_cp": 20,
                    "post_eval_cp": 25,
                    "best_uci": "e2e4",
                    "your_cpl": 5,
                    "rep_cpl": 5,
                    "quality_label": "best",
                }
            ],
        }

    monkeypatch.setattr(api_service, "fetch_game_detail", fake_fetch_game_detail)

    result = asyncio.run(api_service.get_game(44, _="dev-user"))

    assert result.header["id"] == 44
    assert len(result.moves) == 1
    assert result.moves[0].uci_move == "e2e4"


def test_get_game_raises_not_found_for_missing_game(monkeypatch) -> None:
    async def fake_fetch_game_detail(_: int):
        return None

    monkeypatch.setattr(api_service, "fetch_game_detail", fake_fetch_game_detail)

    try:
        asyncio.run(api_service.get_game(999, _="dev-user"))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail["error_code"] == "NOT_FOUND"
    else:
        raise AssertionError("Expected HTTPException for missing game")


def test_get_game_includes_neighbor_fields_on_canonical_get_game(monkeypatch) -> None:
    async def fake_fetch_game_detail(game_id: int):
        assert game_id == 44
        return {
            "header": {"id": 44, "result": "0-1"},
            "moves": [],
            "prev_game_id": 45,
            "next_game_id": 43,
            "prev_game_label": "Alpha vs Beta (2024.01.03)",
            "next_game_label": "Gamma vs Delta (2024.01.01)",
        }

    monkeypatch.setattr(api_service, "fetch_game_detail", fake_fetch_game_detail)

    result = asyncio.run(api_service.get_game(44, _="dev-user"))

    assert result.prev_game_id == 45
    assert result.next_game_id == 43
    assert result.prev_game_label == "Alpha vs Beta (2024.01.03)"
    assert result.next_game_label == "Gamma vs Delta (2024.01.01)"


def test_get_game_neighbor_fields_handle_edge_games(monkeypatch) -> None:
    payloads = {
        100: {"header": {"id": 100}, "moves": [], "prev_game_id": None, "next_game_id": 99, "prev_game_label": None, "next_game_label": "Middle vs Player (2024.01.02)"},
        1: {"header": {"id": 1}, "moves": [], "prev_game_id": 2, "next_game_id": None, "prev_game_label": "Middle vs Player (2024.01.02)", "next_game_label": None},
    }

    async def fake_fetch_game_detail(game_id: int):
        return payloads[game_id]

    monkeypatch.setattr(api_service, "fetch_game_detail", fake_fetch_game_detail)

    newest = asyncio.run(api_service.get_game(100, _="dev-user"))
    oldest = asyncio.run(api_service.get_game(1, _="dev-user"))

    assert newest.prev_game_id is None
    assert newest.next_game_id == 99
    assert newest.prev_game_label is None
    assert newest.next_game_label == "Middle vs Player (2024.01.02)"
    assert oldest.prev_game_id == 2
    assert oldest.next_game_id is None
    assert oldest.prev_game_label == "Middle vs Player (2024.01.02)"
    assert oldest.next_game_label is None


def test_get_game_neighbor_fields_handle_middle_game(monkeypatch) -> None:
    async def fake_fetch_game_detail(game_id: int):
        assert game_id == 99
        return {
            "header": {"id": 99},
            "moves": [],
            "prev_game_id": 100,
            "next_game_id": 1,
            "prev_game_label": "Newest vs Player (2024.01.03)",
            "next_game_label": "Oldest vs Player (2024.01.01)",
        }

    monkeypatch.setattr(api_service, "fetch_game_detail", fake_fetch_game_detail)

    middle = asyncio.run(api_service.get_game(99, _="dev-user"))

    assert middle.prev_game_id == 100
    assert middle.next_game_id == 1
    assert middle.prev_game_label == "Newest vs Player (2024.01.03)"
    assert middle.next_game_label == "Oldest vs Player (2024.01.01)"
