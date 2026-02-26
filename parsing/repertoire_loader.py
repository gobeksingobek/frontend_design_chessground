from __future__ import annotations

from pathlib import Path

import chess.pgn


def _iter_pgn_files(root: Path) -> list[Path]:
    files = list(root.rglob("*.pgn")) + list(root.rglob("*.PGN"))
    return sorted(set(files))


def _detect_side(headers: dict, player_names: list[str]) -> str:
    players = {p.strip().lower() for p in player_names if p.strip()}
    players.add("you")
    white = (headers.get("White") or "").strip().lower()
    black = (headers.get("Black") or "").strip().lower()
    if white in players:
        return "white"
    if black in players:
        return "black"
    return "white"


def load_repertoire_lines(
    repertoire_dir: str,
    file_paths: list[Path] | None = None,
    player_names: list[str] | None = None,
) -> list[dict]:
    root = Path(repertoire_dir)
    if not root.exists():
        raise FileNotFoundError(f"Repertoire directory not found: {root}")

    lines: list[dict] = []
    seen_ids: set[str] = set()
    pgn_files = file_paths or _iter_pgn_files(root)
    for pgn_path in pgn_files:
        with pgn_path.open("r", encoding="utf-8", errors="replace") as handle:
            game_index = 0
            while True:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break
                game_index += 1
                event = (game.headers.get("Event") or "").strip()
                if not event:
                    raise ValueError(
                        f"Missing [Event] tag in repertoire PGN: {pgn_path} game {game_index}"
                    )
                if event in seen_ids:
                    raise ValueError(f"Duplicate repertoire line id [Event]: {event}")
                moves = []
                board = game.board()
                for move in game.mainline_moves():
                    moves.append(
                        {
                            "uci": move.uci(),
                            "san": board.san(move),
                        }
                    )
                    board.push(move)
                is_priority = (game.headers.get("RepertoirePriority") or "").strip() == "1"
                side_to_play = _detect_side(game.headers, player_names or [])
                lines.append(
                    {
                        "line_id": event,
                        "moves": moves,
                        "is_priority": is_priority,
                        "side_to_play": side_to_play,
                        "source_pgn": str(pgn_path),
                    }
                )
                seen_ids.add(event)
    return lines
