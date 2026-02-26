from __future__ import annotations

from pathlib import Path

import chess
from PySide6 import QtCore, QtGui, QtWidgets

LIGHT_SQUARE = "#EEEED2"
DARK_SQUARE = "#769656"
HIGHLIGHT_COLOR = "#baca2b"
ANIM_DURATION_MS = 150


class PngBoardWidget(QtWidgets.QGraphicsView):
    move_attempted = QtCore.Signal(str)

    def __init__(self, piece_dir: str | Path, interactive: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._board = chess.Board()
        self._last_board = self._board.copy(stack=True)
        self._orientation = chess.WHITE
        self._selected_square: int | None = None
        self._interactive = interactive
        self._piece_dir = Path(piece_dir) if piece_dir else Path()
        self._pixmaps: dict[str, QtGui.QPixmap] = {}
        self._scaled_cache: dict[tuple[str, int, float], QtGui.QPixmap] = {}
        self._animating = False
        self._anim_group: QtCore.QParallelAnimationGroup | None = None
        self._load_pixmaps()
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self.setMinimumSize(420, 420)
        self.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._render()

    def set_position(self, board: chess.Board, orientation: chess.Color) -> None:
        next_board = board.copy(stack=True)
        prev_board = self._board.copy(stack=True)
        self._orientation = orientation
        self._last_board = prev_board.copy(stack=True)
        if self._animating and self._anim_group:
            self._anim_group.stop()
            self._anim_group = None
            self._animating = False
        move = self._infer_single_move(prev_board, next_board)
        if move is not None:
            self.animate_move(prev_board, next_board, move.uci())
            return
        self._board = next_board.copy(stack=False)
        self._render()

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        if not enabled:
            self._selected_square = None
        self._render()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._animating and self._anim_group:
            self._anim_group.stop()
            self._anim_group = None
            self._animating = False
        self._scaled_cache.clear()
        self._render()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._animating:
            return
        if not self._interactive:
            return
        square = self._square_from_point(event.position())
        if square is None:
            return
        if self._selected_square is None:
            self._selected_square = square
            self._render()
            return
        if square == self._selected_square:
            self._selected_square = None
            self._render()
            return

        from_square = self._selected_square
        to_square = square
        self._selected_square = None
        move = chess.Move(from_square, to_square)
        if self._is_promotion(move):
            move = chess.Move(from_square, to_square, promotion=chess.QUEEN)
        self._render()
        self.move_attempted.emit(move.uci())

    def _load_pixmaps(self) -> None:
        if not self._piece_dir.exists():
            return
        for code in ["p", "n", "b", "r", "q", "k"]:
            for color in ["w", "b"]:
                name = f"{color}{code}"
                path = self._piece_dir / f"{name}.png"
                if path.exists():
                    self._pixmaps[name] = QtGui.QPixmap(str(path))

    def _render(self) -> None:
        self._render_board(self._board, set())

    def _render_board(self, board: chess.Board, hide_squares: set[int]) -> None:
        self._scene.clear()
        size = min(self.width(), self.height())
        if size <= 0:
            return
        square_size = size / 8
        dpr = self.devicePixelRatioF()
        self._scene.setSceneRect(0, 0, size, size)

        for rank in range(8):
            for file in range(8):
                is_light = (rank + file) % 2 == 1
                color = LIGHT_SQUARE if is_light else DARK_SQUARE
                x, y = self._square_top_left(chess.square(file, rank), square_size)
                rect = QtCore.QRectF(x, y, square_size, square_size)
                self._scene.addRect(rect, QtCore.Qt.NoPen, QtGui.QBrush(QtGui.QColor(color)))

        if self._selected_square is not None:
            x, y = self._square_top_left(self._selected_square, square_size)
            rect = QtCore.QRectF(x, y, square_size, square_size)
            self._scene.addRect(
                rect,
                QtCore.Qt.NoPen,
                QtGui.QBrush(QtGui.QColor(HIGHLIGHT_COLOR)),
            )

        for square in chess.SQUARES:
            if square in hide_squares:
                continue
            piece = board.piece_at(square)
            if not piece:
                continue
            pixmap = self._piece_pixmap(piece, square_size, dpr)
            if pixmap is None:
                continue
            x, y = self._square_top_left(square, square_size)
            item = QtWidgets.QGraphicsPixmapItem(pixmap)
            item.setOffset(x, y)
            self._scene.addItem(item)

    def _piece_pixmap(
        self, piece: chess.Piece, square_size: float, dpr: float
    ) -> QtGui.QPixmap | None:
        symbol = piece.symbol()
        code = symbol.lower()
        color = "w" if symbol.isupper() else "b"
        key = f"{color}{code}"
        pixmap = self._pixmaps.get(key)
        if pixmap is None or pixmap.isNull():
            return None
        cache_key = (key, int(square_size), float(dpr))
        scaled = self._scaled_cache.get(cache_key)
        if scaled is None:
            scaled = pixmap.scaled(
                int(square_size * dpr),
                int(square_size * dpr),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self._scaled_cache[cache_key] = scaled
        return scaled

    def _square_top_left(self, square: int, square_size: float) -> tuple[float, float]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._orientation == chess.WHITE:
            x = file * square_size
            y = (7 - rank) * square_size
        else:
            x = (7 - file) * square_size
            y = rank * square_size
        return x, y

    def _same_position(self, a: chess.Board, b: chess.Board) -> bool:
        return (
            a.board_fen() == b.board_fen()
            and a.turn == b.turn
            and a.castling_rights == b.castling_rights
            and a.ep_square == b.ep_square
        )

    def _infer_single_move(
        self, prev_board: chess.Board, next_board: chess.Board
    ) -> chess.Move | None:
        if self._same_position(prev_board, next_board):
            return None
        if (
            len(next_board.move_stack) == len(prev_board.move_stack) + 1
            and next_board.move_stack
        ):
            move = next_board.move_stack[-1]
            test = prev_board.copy(stack=True)
            if move in test.legal_moves:
                test.push(move)
                if self._same_position(test, next_board):
                    return move
        for move in prev_board.legal_moves:
            test = prev_board.copy(stack=True)
            test.push(move)
            if self._same_position(test, next_board):
                return move
        return None

    def animate_move(
        self, prev_board: chess.Board, next_board: chess.Board, move_uci: str
    ) -> None:
        move = chess.Move.from_uci(move_uci)
        piece = prev_board.piece_at(move.from_square)
        if piece is None:
            self._board = next_board.copy(stack=False)
            self._render()
            return

        size = min(self.width(), self.height())
        if size <= 0:
            self._board = next_board.copy(stack=False)
            self._render()
            return
        square_size = size / 8
        dpr = self.devicePixelRatioF()
        pixmap = self._piece_pixmap(piece, square_size, dpr)
        if pixmap is None:
            self._board = next_board.copy(stack=False)
            self._render()
            return

        self._animating = True
        self._board = prev_board.copy(stack=False)
        hide = {move.from_square, move.to_square}
        self._render_board(prev_board, hide)

        start_x, start_y = self._square_top_left(move.from_square, square_size)
        end_x, end_y = self._square_top_left(move.to_square, square_size)
        moving_item = QtWidgets.QGraphicsPixmapItem(pixmap)
        moving_item.setOffset(0, 0)
        moving_item.setPos(start_x, start_y)
        self._scene.addItem(moving_item)

        animation = QtCore.QVariantAnimation(self)
        animation.setDuration(ANIM_DURATION_MS)
        animation.setStartValue(QtCore.QPointF(start_x, start_y))
        animation.setEndValue(QtCore.QPointF(end_x, end_y))
        animation.setEasingCurve(QtCore.QEasingCurve.Linear)
        animation.valueChanged.connect(lambda value: moving_item.setPos(value))

        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(animation)
        self._anim_group = group

        def _finish() -> None:
            self._animating = False
            self._anim_group = None
            self._board = next_board.copy(stack=False)
            self._render()

        group.finished.connect(_finish)
        group.start()

    def _square_from_point(self, pos: QtCore.QPointF) -> int | None:
        size = min(self.width(), self.height())
        if size <= 0:
            return None
        try:
            scene_pos = self.mapToScene(pos.toPoint())
            x = scene_pos.x()
            y = scene_pos.y()
        except Exception:
            x = pos.x()
            y = pos.y()
        if x < 0 or y < 0 or x >= size or y >= size:
            return None
        square_size = size / 8
        file_index = int(x // square_size)
        rank_index = int(y // square_size)
        if self._orientation == chess.WHITE:
            file = file_index
            rank = 7 - rank_index
        else:
            file = 7 - file_index
            rank = rank_index
        if file < 0 or file > 7 or rank < 0 or rank > 7:
            return None
        return chess.square(file, rank)

    def _is_promotion(self, move: chess.Move) -> bool:
        piece = self._board.piece_at(move.from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return False
        rank = chess.square_rank(move.to_square)
        return rank in {0, 7}
