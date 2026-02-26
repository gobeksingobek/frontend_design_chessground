from __future__ import annotations

import chess
import chess.engine

MATE_SCORE = 100000


def _score_to_cp(score: chess.engine.PovScore | None, pov: chess.Color) -> int | None:
    if score is None:
        return None
    cp = score.pov(pov).score(mate_score=MATE_SCORE)
    if cp is None:
        return None
    return int(cp)


def analyze_game(
    engine: chess.engine.SimpleEngine,
    moves_uci: list[str],
    depth: int,
    player_color: str,
) -> list[dict]:
    board = chess.Board()
    results: list[dict] = []
    pov_player = chess.WHITE if player_color == "white" else chess.BLACK

    limit = chess.engine.Limit(depth=depth)
    for ply_index, move_uci in enumerate(moves_uci, start=1):
        pre_info = engine.analyse(board, limit)
        best_move = None
        if "pv" in pre_info and pre_info["pv"]:
            best_move = pre_info["pv"][0].uci()
        best_eval_cp = _score_to_cp(pre_info.get("score"), pov_player)

        move = chess.Move.from_uci(move_uci)
        mover_is_self = (board.turn == chess.WHITE and player_color == "white") or (
            board.turn == chess.BLACK and player_color == "black"
        )
        board.push(move)

        post_info = engine.analyse(board, limit)
        eval_cp_white = _score_to_cp(post_info.get("score"), chess.WHITE)
        actual_eval_cp = _score_to_cp(post_info.get("score"), pov_player)

        centipawn_loss = None
        if mover_is_self and best_eval_cp is not None and actual_eval_cp is not None:
            centipawn_loss = max(0, best_eval_cp - actual_eval_cp)

        results.append(
            {
                "ply": ply_index,
                "eval_cp": eval_cp_white,
                "best_move_uci": best_move,
                "centipawn_loss": centipawn_loss,
                "is_self": mover_is_self,
            }
        )

    return results
