from __future__ import annotations

import atexit
from typing import Any

import chess
import chess.engine

from analysis.engine_cache import analyze_position

_ENGINE: chess.engine.SimpleEngine | None = None
_ENGINE_MODE = "fixed"
_ENGINE_MAX_TIME_MS = 300


def init_worker(
    stockfish_path: str,
    threads: int,
    hash_mb: int,
    engine_mode: str,
    engine_max_time_ms: int,
) -> None:
    global _ENGINE
    global _ENGINE_MODE
    global _ENGINE_MAX_TIME_MS
    if _ENGINE is not None:
        return
    _ENGINE = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    _ENGINE_MODE = engine_mode or "fixed"
    _ENGINE_MAX_TIME_MS = max(1, int(engine_max_time_ms or 300))
    options: dict[str, Any] = {}
    if threads and threads > 0:
        options["Threads"] = threads
    if hash_mb and hash_mb > 0:
        options["Hash"] = hash_mb
    if options:
        try:
            _ENGINE.configure(options)
        except Exception:
            pass
    atexit.register(_shutdown_engine)


def _shutdown_engine() -> None:
    global _ENGINE
    if _ENGINE is None:
        return
    try:
        _ENGINE.quit()
    except Exception:
        pass
    _ENGINE = None


def analyze_fen_task(args: tuple[int, str, int]) -> tuple[int, str | None, int | None, dict | None]:
    pos_id, fen, depth = args
    if _ENGINE is None:
        return pos_id, None, None, None
    try:
        board = chess.Board(fen)
        best_uci, eval_cp, wdl = analyze_position(
            _ENGINE,
            board,
            depth,
            mode=_ENGINE_MODE,
            max_time_ms=_ENGINE_MAX_TIME_MS,
        )
        return pos_id, best_uci, eval_cp, wdl
    except Exception:
        return pos_id, None, None, None
