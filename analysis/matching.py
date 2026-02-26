from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchResult:
    matched_line_id: str | None
    max_matched_ply: int
    deviation_ply_self: int | None
    deviation_ply_opp: int | None
    tie_line_ids: list[str]


def _prefix_match_moves(game_moves: list[str], line_moves: list[str]) -> int:
    max_compare = min(len(game_moves), len(line_moves))
    count = 0
    for idx in range(max_compare):
        if game_moves[idx] == line_moves[idx]:
            count += 1
        else:
            break
    return count


def _prefix_match_positions(game_pos_ids: list[int], line_pos_ids: list[int]) -> int:
    max_compare = min(len(game_pos_ids), len(line_pos_ids))
    count = 0
    for idx in range(max_compare):
        if game_pos_ids[idx] == line_pos_ids[idx]:
            count += 1
        else:
            break
    return count


def _first_deviation_ply(
    game_moves: list[str], line_moves: list[str], player_color: str
) -> tuple[int | None, int | None]:
    max_compare = min(len(game_moves), len(line_moves))
    first_self = None
    first_opp = None

    for idx in range(max_compare):
        if game_moves[idx] != line_moves[idx]:
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
    return first_self, first_opp


def find_best_match(
    game_moves: list[str],
    game_pos_ids: list[int],
    lines: list[dict],
    player_color: str,
    mode: str,
) -> MatchResult:
    best_len = 0
    tie_line_ids: list[str] = []
    best_line: dict | None = None

    for line in lines:
        if mode == "TRANSPOSITION":
            match_len = _prefix_match_positions(game_pos_ids, line["pos_ids"])
        else:
            match_len = _prefix_match_moves(game_moves, line["moves_uci"])

        if match_len > best_len:
            best_len = match_len
            tie_line_ids = [line["line_id"]]
            best_line = line
        elif match_len == best_len:
            tie_line_ids.append(line["line_id"])

    if not tie_line_ids:
        return MatchResult(None, 0, None, None, [])

    matched_line_id = min(tie_line_ids)
    matched_line = None
    if best_line and best_line["line_id"] == matched_line_id:
        matched_line = best_line
    else:
        for line in lines:
            if line["line_id"] == matched_line_id:
                matched_line = line
                break

    if matched_line is None:
        return MatchResult(matched_line_id, best_len, None, None, tie_line_ids)

    dev_self, dev_opp = _first_deviation_ply(game_moves, matched_line["moves_uci"], player_color)
    return MatchResult(matched_line_id, best_len, dev_self, dev_opp, tie_line_ids)