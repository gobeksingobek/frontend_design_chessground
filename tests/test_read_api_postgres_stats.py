from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend import read_api


@dataclass
class _Settings:
    data_backend: str = "postgres"
    postgres_dsn: str = "postgres://fake"


class _FakeConn:
    async def fetchval(self, query: str, *args):
        if "FROM repertoire_lines" in query and "is_priority" not in query:
            return 3
        if "FROM games" in query:
            return 5
        if "FROM matches WHERE compliance = 'FULLY_COMPLIANT'" in query:
            return 2
        if "FROM matches" in query:
            return 4
        if "repertoire_lines WHERE is_priority = TRUE" in query:
            return 1
        if "trainer_line_state" in query:
            return 2
        return 0

    async def fetch(self, query: str, *args):
        if "FROM games g" in query and "LEFT JOIN matches" in query:
            return [
                {
                    "id": 11,
                    "date": "2024-02-12",
                    "white": "Alice",
                    "black": "Bob",
                    "result": "1-0",
                    "white_elo": 1602,
                    "black_elo": 1501,
                    "player_color": "white",
                    "is_daily": 0,
                    "time_control": "600+0",
                    "line_id": "line-a",
                    "max_matched_ply": 2,
                    "deviation_ply_you": None,
                    "deviation_ply_opp": 4,
                    "compliance": "FULLY_COMPLIANT",
                    "matching_mode": "strict",
                    "opponent_dev_to_known": 1,
                }
            ]
        if "FROM analysis_ply ap" in query:
            return [{"game_id": 11, "post_eval_cp": 18}]
        if "FROM game_positions gp" in query and "time_spent_seconds" in query:
            return [
                {
                    "game_id": 11,
                    "ply": 1,
                    "time_spent_seconds": 3.0,
                    "time_spent_fraction": 0.2,
                    "is_self": 1,
                    "is_daily": 0,
                    "repertoire_class": "IN_REPERTOIRE_MAIN",
                    "max_matched_ply": 2,
                },
                {
                    "game_id": 11,
                    "ply": 3,
                    "time_spent_seconds": 7.0,
                    "time_spent_fraction": 0.45,
                    "is_self": 1,
                    "is_daily": 0,
                    "repertoire_class": "OUT_OF_REPERTOIRE",
                    "max_matched_ply": 2,
                },
            ]
        if "GROUP BY m.matched_line_id" in query:
            return [{"line_id": "line-a", "in_other": 1, "in_total": 2, "out_total": 1}]
        if "FROM insights" in query:
            return [{"category": "prep", "title": "Top miss", "details": "detail", "data_json": '{"n": 1}'}]
        if "FROM review_items" in query:
            return [{"line_id": "line-a", "reason": "coverage", "detail": "missing move"}]
        return []

    async def close(self):
        return None


async def _fake_connect(_dsn: str):
    return _FakeConn()


def test_postgres_stats_endpoints_return_expected_shapes(monkeypatch) -> None:
    monkeypatch.setattr(read_api, "SETTINGS", _Settings())
    monkeypatch.setattr(read_api.asyncpg, "connect", _fake_connect)

    summary = asyncio.run(read_api.fetch_overview_summary())
    assert summary["lines"] == 3
    assert set(summary.keys()) == {
        "lines",
        "manual_priority",
        "auto_priority",
        "games",
        "matched",
        "fully_compliant",
    }

    line_stats = asyncio.run(read_api.fetch_lines_stats())
    assert isinstance(line_stats, list)
    assert line_stats
    assert {"key", "total_games", "compliance_rate", "in_rep_other_rate"}.issubset(line_stats[0].keys())

    time_stats = asyncio.run(read_api.fetch_time_usage_stats("self_vs_opp"))
    assert isinstance(time_stats, dict)
    assert time_stats["pivot"] == "self_vs_opp"
    assert isinstance(time_stats["buckets"], list)
    assert {"total_games"}.issubset(time_stats["totals"].keys())

    rating_stats = asyncio.run(read_api.fetch_rating_band_stats(100))
    assert isinstance(rating_stats, list)
    assert rating_stats
    assert {"white_band", "black_band", "total_games", "compliance_rate"}.issubset(rating_stats[0].keys())

    insights = asyncio.run(read_api.fetch_insights())
    assert insights[0]["category"] == "prep"
    assert insights[0]["title"] == "Top miss"
    assert insights[0]["data"] == {"n": 1}

    review_items = asyncio.run(read_api.fetch_review_items())
    assert review_items == [{"line_id": "line-a", "reason": "coverage", "detail": "missing move"}]
