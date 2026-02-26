from __future__ import annotations

import chess
import chess.polyglot


def normalize_fen(board: chess.Board) -> str:
    parts = board.fen().split(" ")
    return " ".join(parts[:4])


def material_key(board: chess.Board) -> str:
    counts = {
        chess.PAWN: "P",
        chess.KNIGHT: "N",
        chess.BISHOP: "B",
        chess.ROOK: "R",
        chess.QUEEN: "Q",
    }
    white_parts = []
    black_parts = []
    for piece_type, symbol in counts.items():
        white_parts.append(f"{symbol}{len(board.pieces(piece_type, chess.WHITE))}")
        black_parts.append(f"{symbol}{len(board.pieces(piece_type, chess.BLACK))}")
    return "W:" + "".join(white_parts) + "|B:" + "".join(black_parts)


def zobrist_hash(board: chess.Board) -> int:
    value = chess.polyglot.zobrist_hash(board)
    if value >= (1 << 63):
        value -= 1 << 64
    return value
