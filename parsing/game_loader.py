from __future__ import annotations

from pathlib import Path

import chess
import chess.pgn

from parsing import clock_parser


def _iter_pgn_files(root: Path) -> list[Path]:
    files = list(root.rglob("*.pgn")) + list(root.rglob("*.PGN"))
    return sorted(set(files))


def _parse_pgn_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    parts = date_str.split(".")
    if len(parts) != 3:
        return date_str
    year, month, day = parts
    if "?" in year or "?" in month or "?" in day:
        return date_str
    return f"{year}-{month}-{day}"


def _resolve_player_color(tags: dict, player_names: list[str]) -> str | None:
    if not player_names:
        return None
    white = (tags.get("White") or "").strip()
    black = (tags.get("Black") or "").strip()
    for name in player_names:
        if white.casefold() == name.casefold():
            return "white"
    for name in player_names:
        if black.casefold() == name.casefold():
            return "black"
    return None


def _is_daily_game(tags: dict) -> bool:
    event = (tags.get("Event") or "").lower()
    time_control = (tags.get("TimeControl") or "").lower()
    if "daily" in event or "correspondence" in event:
        return True
    if "day" in time_control:
        return True
    if "/" in time_control:
        return True
    return False


def load_games_from_dir(
    games_dir: str, player_names: list[str], file_paths: list[Path] | None = None
) -> list[dict]:
    root = Path(games_dir)
    if not root.exists():
        raise FileNotFoundError(f"Games directory not found: {root}")

    games: list[dict] = []
    pgn_files = file_paths or _iter_pgn_files(root)
    for pgn_path in pgn_files:
        with pgn_path.open("r", encoding="utf-8", errors="replace") as handle:
            while True:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break

                tags = dict(game.headers)
                player_color = _resolve_player_color(tags, player_names)
                if player_color is None:
                    continue

                time_control = tags.get("TimeControl")
                base_seconds, increment_seconds = clock_parser.parse_time_control(time_control)
                is_daily = _is_daily_game(tags)

                board = game.board()
                moves: list[dict] = []
                moves_uci: list[str] = []

                for node in game.mainline():
                    move = node.move
                    ply = board.ply() + 1
                    move_uci = move.uci()
                    move_san = board.san(move)
                    is_white_move = board.turn == chess.WHITE
                    is_self = (player_color == "white" and is_white_move) or (
                        player_color == "black" and not is_white_move
                    )
                    clock_seconds = clock_parser.parse_clock_seconds(node.comment)

                    moves.append(
                        {
                            "ply": ply,
                            "move_uci": move_uci,
                            "move_san": move_san,
                            "is_self": is_self,
                            "is_white": is_white_move,
                            "clock_seconds": clock_seconds,
                            "time_spent_seconds": None,
                        }
                    )
                    moves_uci.append(move_uci)
                    board.push(move)

                last_white = base_seconds
                last_black = base_seconds
                for move in moves:
                    current_clock = move.get("clock_seconds")
                    if move["is_white"]:
                        move["time_spent_seconds"] = clock_parser.compute_time_spent(
                            last_white, current_clock, increment_seconds
                        )
                        if current_clock is not None:
                            last_white = current_clock
                    else:
                        move["time_spent_seconds"] = clock_parser.compute_time_spent(
                            last_black, current_clock, increment_seconds
                        )
                        if current_clock is not None:
                            last_black = current_clock
                    move.pop("is_white", None)

                games.append(
                    {
                        "tags": tags,
                        "moves": moves,
                        "moves_uci": moves_uci,
                        "player_color": player_color,
                        "is_daily": is_daily,
                        "time_control": time_control,
                        "date": _parse_pgn_date(tags.get("Date")),
                        "source_pgn": str(pgn_path),
                    }
                )

    return games
