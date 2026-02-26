from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchResult:
    line_id: str | None
    max_matched_ply: int
    first_opponent_deviation_ply: int | None
    first_self_deviation_ply: int | None


def _compute_match(moves: list[str], line_moves: list[str], player_color: str) -> MatchResult:
    max_compare = min(len(moves), len(line_moves))

    max_matched_ply = 0
    for idx in range(max_compare):
        if moves[idx] == line_moves[idx]:
            max_matched_ply += 1
        else:
            break

    first_self = None
    first_opp = None
    for idx in range(max_compare):
        if moves[idx] != line_moves[idx]:
            ply = idx + 1
            mover_is_white = (idx % 2) == 0
            mover_is_self = (player_color == "white" and mover_is_white) or (
                player_color == "black" and not mover_is_white
            )
            if mover_is_self and first_self is None:
                first_self = ply
            if not mover_is_self and first_opp is None:
                first_opp = ply
            if first_self is not None and first_opp is not None:
                break
    return MatchResult(None, max_matched_ply, first_opp, first_self)


def match_game(moves: list[str], repertoire_lines: list[dict], player_color: str) -> MatchResult:
    best_result: MatchResult | None = None
    best_line_id: str | None = None

    for line in repertoire_lines:
        result = _compute_match(moves, line["moves_uci"], player_color)
        if best_result is None or result.max_matched_ply > best_result.max_matched_ply:
            best_result = result
            best_line_id = line["line_id"]

    if best_result is None:
        return MatchResult(None, 0, None, None)

    best_result.line_id = best_line_id
    return best_result