from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import chess
import chess.engine

MATE_SCORE = 100000


def engine_identity(engine: chess.engine.SimpleEngine, engine_path: str) -> str:
    hasher = hashlib.sha1()
    with open(engine_path, "rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    file_hash = hasher.hexdigest()
    engine_id = engine.id.get("name", "unknown")
    return f"{engine_id}:{file_hash}"


def score_to_cp(score: chess.engine.PovScore | None) -> int | None:
    if score is None:
        return None
    cp = score.pov(chess.WHITE).score(mate_score=MATE_SCORE)
    if cp is None:
        return None
    return int(cp)


def analyze_position(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    depth: int,
    mode: str = "fixed",
    max_time_ms: int = 300,
) -> tuple[str | None, int | None, dict | None]:
    if mode == "adaptive":
        limit = chess.engine.Limit(depth=depth, time=max(1, int(max_time_ms)) / 1000.0)
    else:
        limit = chess.engine.Limit(depth=depth)
    info = engine.analyse(board, limit)
    best_move = None
    if info.get("pv"):
        best_move = info["pv"][0].uci()
    eval_cp = score_to_cp(info.get("score"))
    wdl = None
    if info.get("wdl") is not None:
        wdl = {
            "win": info["wdl"].pov(chess.WHITE).win,
            "draw": info["wdl"].pov(chess.WHITE).draw,
            "loss": info["wdl"].pov(chess.WHITE).loss,
        }
    return best_move, eval_cp, wdl


def cache_entries_to_rows(
    entries: dict[int, dict], depth: int, engine_id: str
) -> list[tuple]:
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for pos_id, data in entries.items():
        rows.append(
            (
                pos_id,
                depth,
                engine_id,
                data.get("best_uci"),
                data.get("eval_cp"),
                data.get("wdl_json"),
                now,
            )
        )
    return rows
