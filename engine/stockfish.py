from __future__ import annotations

from contextlib import contextmanager

import chess.engine


@contextmanager
def stockfish_engine(path: str):
    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        yield engine
    finally:
        engine.quit()