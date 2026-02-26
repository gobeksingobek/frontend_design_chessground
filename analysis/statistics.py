from __future__ import annotations

from collections import defaultdict

from analysis import time_analysis
from storage import queries


RESULT_WIN = "win"
RESULT_LOSS = "loss"
RESULT_DRAW = "draw"


def _result_for_player(result: str | None, player_color: str | None) -> str | None:
    if not result or not player_color:
        return None
    if result == "1-0":
        return RESULT_WIN if player_color == "white" else RESULT_LOSS
    if result == "0-1":
        return RESULT_WIN if player_color == "black" else RESULT_LOSS
    if result == "1/2-1/2":
        return RESULT_DRAW
    return None


def _rating_band(value: int | None, band_size: int) -> str:
    if value is None:
        return "Unknown"
    start = (value // band_size) * band_size
    end = start + band_size - 1
    return f"{start}-{end}"


def _deviation_ply(first_self: int | None, first_opp: int | None) -> int | None:
    if first_self is None and first_opp is None:
        return None
    if first_self is None:
        return first_opp
    if first_opp is None:
        return first_self
    return min(first_self, first_opp)


def _init_stat_entry() -> dict:
    return {
        "total_games": 0,
        "fully_compliant": 0,
        "deviation_total": 0,
        "deviation_count": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "eval_total": 0,
        "eval_count": 0,
        "in_book_total": 0,
        "in_book_count": 0,
        "out_book_total": 0,
        "out_book_count": 0,
        "in_book_frac_total": 0,
        "in_book_frac_count": 0,
        "out_book_frac_total": 0,
        "out_book_frac_count": 0,
        "opp_dev_known": 0,
        "opp_dev_total": 0,
    }


def _finalize_stats(stats: dict) -> list[dict]:
    results = []
    for key, entry in stats.items():
        compliance_rate = (
            entry["fully_compliant"] / entry["total_games"]
            if entry["total_games"]
            else None
        )
        avg_deviation_ply = (
            entry["deviation_total"] / entry["deviation_count"]
            if entry["deviation_count"]
            else None
        )
        avg_eval_exit = (
            entry["eval_total"] / entry["eval_count"] if entry["eval_count"] else None
        )
        in_book_avg = (
            entry["in_book_total"] / entry["in_book_count"]
            if entry["in_book_count"]
            else None
        )
        out_book_avg = (
            entry["out_book_total"] / entry["out_book_count"]
            if entry["out_book_count"]
            else None
        )
        in_book_frac_avg = (
            entry["in_book_frac_total"] / entry["in_book_frac_count"]
            if entry["in_book_frac_count"]
            else None
        )
        out_book_frac_avg = (
            entry["out_book_frac_total"] / entry["out_book_frac_count"]
            if entry["out_book_frac_count"]
            else None
        )
        opp_dev_known_rate = (
            entry["opp_dev_known"] / entry["opp_dev_total"]
            if entry["opp_dev_total"]
            else None
        )

        result = {
            "key": key,
            "total_games": entry["total_games"],
            "compliance_rate": compliance_rate,
            "avg_deviation_ply": avg_deviation_ply,
            "wins": entry["wins"],
            "losses": entry["losses"],
            "draws": entry["draws"],
            "avg_eval_exit": avg_eval_exit,
            "in_book_avg": in_book_avg,
            "out_book_avg": out_book_avg,
            "in_book_frac_avg": in_book_frac_avg,
            "out_book_frac_avg": out_book_frac_avg,
            "opp_dev_known_rate": opp_dev_known_rate,
        }
        results.append(result)
    return results


def _accumulate_game(entry: dict, game: dict, eval_at_exit: dict, time_by_game: dict) -> None:
    entry["total_games"] += 1
    if game.get("compliance") == "FULLY_COMPLIANT":
        entry["fully_compliant"] += 1

    deviation = _deviation_ply(
        game.get("deviation_ply_you"), game.get("deviation_ply_opp")
    )
    if deviation is not None:
        entry["deviation_total"] += deviation
        entry["deviation_count"] += 1

    outcome = _result_for_player(game.get("result"), game.get("player_color"))
    if outcome == RESULT_WIN:
        entry["wins"] += 1
    elif outcome == RESULT_LOSS:
        entry["losses"] += 1
    elif outcome == RESULT_DRAW:
        entry["draws"] += 1

    eval_exit = eval_at_exit.get(game["id"])
    if eval_exit is not None:
        entry["eval_total"] += eval_exit
        entry["eval_count"] += 1

    time_entry = time_by_game.get(game["id"])
    if time_entry:
        entry["in_book_total"] += time_entry["in_book_total"]
        entry["in_book_count"] += time_entry["in_book_count"]
        entry["out_book_total"] += time_entry["out_book_total"]
        entry["out_book_count"] += time_entry["out_book_count"]
        entry["in_book_frac_total"] += time_entry.get("in_book_frac_total", 0)
        entry["in_book_frac_count"] += time_entry.get("in_book_frac_count", 0)
        entry["out_book_frac_total"] += time_entry.get("out_book_frac_total", 0)
        entry["out_book_frac_count"] += time_entry.get("out_book_frac_count", 0)

    if game.get("deviation_ply_opp") is not None:
        entry["opp_dev_total"] += 1
        if game.get("opponent_dev_to_known"):
            entry["opp_dev_known"] += 1


def aggregate_by_line(conn) -> list[dict]:
    games = queries.fetch_game_summaries(conn)
    eval_at_exit = queries.fetch_eval_at_exit(conn)
    time_rows = queries.fetch_time_usage_rows(conn)
    time_by_game = time_analysis.compute_time_usage_by_game(time_rows)
    class_counts = queries.fetch_repertoire_class_counts_by_line(conn)

    stats: dict[str | None, dict] = {}
    for game in games:
        key = game.get("line_id")
        if key is None:
            continue
        entry = stats.setdefault(key, _init_stat_entry())
        _accumulate_game(entry, game, eval_at_exit, time_by_game)

    results = _finalize_stats(stats)
    for result in results:
        counts = class_counts.get(result["key"] or None, {})
        in_other = counts.get("in_other") or 0
        in_total = counts.get("in_total") or 0
        result["in_rep_other_rate"] = in_other / in_total if in_total else None
    return results


def aggregate_by_month(conn) -> list[dict]:
    games = queries.fetch_game_summaries(conn)
    eval_at_exit = queries.fetch_eval_at_exit(conn)
    time_rows = queries.fetch_time_usage_rows(conn)
    time_by_game = time_analysis.compute_time_usage_by_game(time_rows)

    stats: dict[str | None, dict] = {}
    for game in games:
        date = game.get("date") or ""
        month = date[:7] if len(date) >= 7 else "Unknown"
        entry = stats.setdefault(month, _init_stat_entry())
        _accumulate_game(entry, game, eval_at_exit, time_by_game)

    return _finalize_stats(stats)


def aggregate_by_rating_band(conn, band_size: int = 100) -> list[dict]:
    games = queries.fetch_game_summaries(conn)
    eval_at_exit = queries.fetch_eval_at_exit(conn)
    time_rows = queries.fetch_time_usage_rows(conn)
    time_by_game = time_analysis.compute_time_usage_by_game(time_rows)

    stats: dict[tuple[str, str], dict] = {}
    for game in games:
        white_band = _rating_band(game.get("white_elo"), band_size)
        black_band = _rating_band(game.get("black_elo"), band_size)
        key = (white_band, black_band)
        entry = stats.setdefault(key, _init_stat_entry())
        _accumulate_game(entry, game, eval_at_exit, time_by_game)

    results = _finalize_stats(stats)
    for result in results:
        key = result["key"]
        if isinstance(key, tuple):
            result["white_band"], result["black_band"] = key
        result.pop("key", None)
    return results
