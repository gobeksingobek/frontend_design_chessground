from __future__ import annotations

from pathlib import Path
from io import StringIO

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
    pgn_files = file_paths or _iter_pgn_files(root)
    for pgn_path in pgn_files:
        text = pgn_path.read_text(encoding="utf-8", errors="replace")
        lines.extend(load_repertoire_pgn_text(text, pgn_path.name, player_names))
    return lines


def load_repertoire_pgn_text(
    pgn_text: str, source_name: str, player_names: list[str] | None = None
) -> list[dict]:
    handle = StringIO(pgn_text)
    lines: list[dict] = []
    game_index = 0
    while True:
        game = chess.pgn.read_game(handle)
        if game is None:
            break
        game_index += 1
        event = (game.headers.get("Event") or "").strip()
        root_key = (game.headers.get("RepertoireRoot") or "root").strip()
        moves = []
        board = game.board()
        for move in game.mainline_moves():
            moves.append({"uci": move.uci(), "san": board.san(move)})
            board.push(move)
        lines.append(
            {
                "label": event or f"{Path(source_name).stem} #{game_index}",
                "root_key": root_key,
                "moves": moves,
                "is_priority": (game.headers.get("RepertoirePriority") or "").strip() == "1",
                "side_to_play": _detect_side(game.headers, player_names or []),
                "source_pgn": f"artifact://{source_name}",
            }
        )
    return lines
