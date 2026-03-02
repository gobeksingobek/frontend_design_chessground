from __future__ import annotations

import chess
from PySide6 import QtCore, QtGui, QtWidgets

from analysis.classification import repertoire_eval_message
from gui.widgets.board_widget import PngBoardWidget

QUALITY_COLORS = {
    "BLUNDER": "#d84c4c",
    "MISTAKE": "#f39c12",
    "INACCURACY": "#f1c40f",
    "GOOD": "#b8e0a3",
    "EXCELLENT": "#9adf9a",
    "BEST": "#2ecc71",
}
BOOK_BORDER = "#8B5A2B"
GAME_DETAILS_SPLIT_LEFT = 1
GAME_DETAILS_SPLIT_RIGHT = 1


class EvalBarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._eval_cp: int | None = None
        self.setMinimumWidth(32)

    def set_eval(self, eval_cp: int | None) -> None:
        self._eval_cp = eval_cp
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor("#222222"))

        if self._eval_cp is None:
            return

        clamp = max(min(self._eval_cp, 1000), -1000)
        ratio = (clamp + 1000) / 2000
        white_height = int(rect.height() * ratio)
        white_rect = QtCore.QRect(
            rect.left(), rect.bottom() - white_height + 1, rect.width(), white_height
        )
        painter.fillRect(white_rect, QtGui.QColor("#f2f2f2"))

        # Draw eval text near the white/black boundary on the advantaged side.
        value = self._eval_cp / 100.0
        if abs(value) < 0.05:
            text = "0.0"
        elif value > 0:
            text = f"+{value:.1f}"
        else:
            text = f"{value:.1f}"

        font = painter.font()
        font.setPointSize(max(8, font.pointSize()))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_height = metrics.height()
        text_width = metrics.horizontalAdvance(text)

        boundary_y = rect.bottom() - white_height + 1
        x = rect.center().x() - text_width // 2
        margin = 2

        if self._eval_cp >= 0:
            y = boundary_y + text_height + margin
            y = min(y, rect.bottom() - margin)
            y = max(y, rect.top() + text_height)
            text_color = QtGui.QColor("#111111")
            shadow_color = QtGui.QColor(255, 255, 255, 140)
        else:
            y = boundary_y - margin
            y = max(y, rect.top() + text_height)
            y = min(y, rect.bottom() - margin)
            text_color = QtGui.QColor("#f2f2f2")
            shadow_color = QtGui.QColor(0, 0, 0, 160)

        painter.setPen(shadow_color)
        painter.drawText(x + 1, y + 1, text)
        painter.setPen(text_color)
        painter.drawText(x, y, text)

        pen = QtGui.QPen(QtGui.QColor("#111111"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))


class MoveColorDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index) -> None:
        color = index.data(QtCore.Qt.UserRole)
        is_book = bool(index.data(QtCore.Qt.UserRole + 1))
        if color:
            painter.fillRect(option.rect, QtGui.QColor(color))

        super().paint(painter, option, index)

        if is_book:
            pen = QtGui.QPen(QtGui.QColor(BOOK_BORDER))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))


class GameDetailsTab(QtWidgets.QWidget):
    def __init__(self, controller, show_game_selector: bool = True) -> None:
        super().__init__()
        self.controller = controller
        self.show_game_selector = show_game_selector
        self.current_game_id: int | None = None
        self.current_header: dict | None = None
        self.moves: list[dict] = []
        self.boards: list[chess.Board] = []
        self.current_ply = 0
        self._updating_selection = False
        self._reanalysis_worker: _ReanalysisWorker | None = None
        self._rep_cpl_worker: _RepCplWorker | None = None
        self._rep_cpl_inflight: tuple[int, int] | None = None

        layout = QtWidgets.QVBoxLayout(self)

        selector_row = QtWidgets.QHBoxLayout()
        self.game_label = QtWidgets.QLabel("Game")
        selector_row.addWidget(self.game_label)
        self.game_combo = QtWidgets.QComboBox()
        selector_row.addWidget(self.game_combo, 1)
        self.reanalyze_button = QtWidgets.QPushButton("Reanalyze game")
        selector_row.addWidget(self.reanalyze_button)
        self.status_label = QtWidgets.QLabel("")
        selector_row.addWidget(self.status_label)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        board_row = QtWidgets.QHBoxLayout()
        self.board_widget = PngBoardWidget(self.controller.config.piece_dir)
        self.eval_bar = EvalBarWidget()
        board_row.addWidget(self.board_widget, 1)
        board_row.addWidget(self.eval_bar)
        left_layout.addLayout(board_row)

        left_layout.addStretch()

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)

        self.game_info = QtWidgets.QLabel("")
        self.game_info.setWordWrap(True)
        right_layout.addWidget(self.game_info)

        prompt_box = QtWidgets.QGroupBox("Repertoire prompt")
        prompt_layout = QtWidgets.QVBoxLayout(prompt_box)
        self.prompt_line = QtWidgets.QLabel("")
        self.prompt_line.setWordWrap(True)
        self.prompt_move = QtWidgets.QLabel("")
        self.prompt_move.setWordWrap(True)
        self.create_sideline_button = QtWidgets.QPushButton("Create sideline at deviation")
        prompt_layout.addWidget(self.prompt_line)
        prompt_layout.addWidget(self.prompt_move)
        prompt_layout.addWidget(self.create_sideline_button)
        right_layout.addWidget(prompt_box)

        self.move_table = QtWidgets.QTableWidget()
        self.move_table.setColumnCount(7)
        self.move_table.setHorizontalHeaderLabels(
            [
                "Ply",
                "Move",
                "Repertoire",
                "Quality",
                "CPL",
                "Rep CPL",
                "Best",
            ]
        )
        self.move_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.move_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.move_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.move_table.horizontalHeader().setStretchLastSection(True)
        self.move_table.setItemDelegate(MoveColorDelegate(self.move_table))
        right_layout.addWidget(self.move_table, 1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, GAME_DETAILS_SPLIT_LEFT)
        splitter.setStretchFactor(1, GAME_DETAILS_SPLIT_RIGHT)
        QtCore.QTimer.singleShot(
            0,
            lambda: splitter.setSizes(
                [GAME_DETAILS_SPLIT_LEFT, GAME_DETAILS_SPLIT_RIGHT]
            ),
        )

        self.game_combo.currentIndexChanged.connect(self._load_current_game)
        self.reanalyze_button.clicked.connect(self._reanalyze_game)
        self.create_sideline_button.clicked.connect(self._create_sideline_at_deviation)
        self.move_table.currentCellChanged.connect(self._on_move_selected)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self, activated=self._next_move)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self, activated=self._prev_move)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self, activated=self._go_end)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self, activated=self._go_start)

        if not self.show_game_selector:
            self.game_label.hide()
            self.game_combo.hide()

        self.refresh()

    @staticmethod
    def _stop_thread(
        thread: QtCore.QThread | None,
        *,
        force: bool = True,
        timeout_ms: int = 1200,
    ) -> bool:
        if thread is None:
            return True
        if not thread.isRunning():
            return True
        try:
            thread.requestInterruption()
        except Exception:
            pass
        if thread.wait(timeout_ms):
            return True
        if not force:
            return False
        try:
            thread.terminate()
        except Exception:
            pass
        return thread.wait(timeout_ms)

    def has_active_workers(self) -> bool:
        return bool(
            (self._reanalysis_worker and self._reanalysis_worker.isRunning())
            or (self._rep_cpl_worker and self._rep_cpl_worker.isRunning())
        )

    def shutdown_workers(self, force: bool = True) -> None:
        self.reanalyze_button.setEnabled(False)
        self.create_sideline_button.setEnabled(False)
        self._stop_thread(self._reanalysis_worker, force=force)
        self._stop_thread(self._rep_cpl_worker, force=force)
        self._reanalysis_worker = None
        self._rep_cpl_worker = None
        self._rep_cpl_inflight = None

    def refresh(self) -> None:
        games = self.controller.get_games_list()
        current_id = self.current_game_id

        if self.show_game_selector:
            self.game_combo.blockSignals(True)
            self.game_combo.clear()
            for game in games:
                label = (
                    f"{game.get('date') or ''} {game.get('white') or ''} vs "
                    f"{game.get('black') or ''} {game.get('result') or ''}"
                )
                self.game_combo.addItem(label, game.get("id"))
            self.game_combo.blockSignals(False)

            if current_id:
                idx = self.game_combo.findData(current_id)
                if idx >= 0:
                    self.game_combo.setCurrentIndex(idx)
                    self._load_current_game()
                    return
            if self.game_combo.count() > 0:
                self.game_combo.setCurrentIndex(0)
                self._load_current_game()
            return

        if current_id is None:
            return
        game_ids = {int(game.get("id")) for game in games if game.get("id") is not None}
        if current_id in game_ids:
            self._load_game(current_id)
        else:
            self.current_game_id = None
            self.current_header = None
            self.moves = []
            self.boards = [chess.Board()]
            self.move_table.clearContents()
            self.move_table.setRowCount(0)
            self.board_widget.set_position(chess.Board(), chess.WHITE)
            self.game_info.setText("")
            self.prompt_line.setText("")
            self.prompt_move.setText("")
            self.create_sideline_button.setEnabled(False)
            self.eval_bar.set_eval(None)

    def _load_current_game(self) -> None:
        game_id = self.game_combo.currentData()
        if game_id is None:
            return
        self._load_game(int(game_id))

    def load_game_by_id(self, game_id: int) -> bool:
        if game_id is None:
            return False
        if self.show_game_selector:
            idx = self.game_combo.findData(int(game_id))
            if idx < 0:
                self.refresh()
                idx = self.game_combo.findData(int(game_id))
            if idx < 0:
                return False
            self.game_combo.blockSignals(True)
            self.game_combo.setCurrentIndex(idx)
            self.game_combo.blockSignals(False)
        return self._load_game(int(game_id))

    def _load_game(self, game_id: int) -> bool:
        self.current_game_id = int(game_id)
        self.status_label.setText("")

        header = self.controller.get_game_header(self.current_game_id)
        moves = self.controller.get_game_moves(self.current_game_id)
        if not header:
            return False
        self.current_header = header
        self.moves = moves

        player_color = header.get("player_color") or "white"
        orientation = chess.WHITE if player_color == "white" else chess.BLACK

        self._build_boards()
        self._populate_moves_table()
        self._update_game_info()
        self._update_prompt()

        self.set_current_ply(0, orientation)
        self._ensure_deviation_rep_cpl()
        return True

    def _build_boards(self) -> None:
        self.boards = [chess.Board()]
        board = chess.Board()
        for move in self.moves:
            uci = move.get("uci_move")
            if not uci:
                continue
            board.push(chess.Move.from_uci(uci))
            self.boards.append(board.copy(stack=False))

    def _populate_moves_table(self) -> None:
        self._updating_selection = True
        self.move_table.clearContents()
        self.move_table.setRowCount(len(self.moves))

        for row_index, move in enumerate(self.moves):
            ply = move.get("ply")
            san = move.get("san_move") or move.get("uci_move") or ""
            rep_class = move.get("repertoire_class") or ""
            quality = move.get("quality_label") or ""
            your_cpl = move.get("your_cpl")
            rep_cpl = (
                move.get("rep_cpl")
                if self._should_show_rep_cpl_for_ply(ply)
                else None
            )
            best = move.get("best_uci") or ""

            values = [
                str(ply or ""),
                san,
                rep_class,
                quality,
                f"{your_cpl}" if your_cpl is not None else "",
                f"{rep_cpl}" if rep_cpl is not None else "",
                best,
            ]

            color = QUALITY_COLORS.get(quality)
            is_book = rep_class in {"IN_REPERTOIRE_MAIN", "IN_REPERTOIRE_OTHER"}
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setData(QtCore.Qt.UserRole, color)
                item.setData(QtCore.Qt.UserRole + 1, is_book)
                self.move_table.setItem(row_index, col_index, item)

        self._updating_selection = False

    def _update_game_info(self) -> None:
        header = self.current_header or {}
        tags = ", ".join(header.get("tags") or []) or "None"
        self.game_info.setText(
            " | ".join(
                [
                    f"Line: {header.get('line_id') or 'N/A'}",
                    f"Compliance: {header.get('compliance') or 'N/A'}",
                    f"Match: {header.get('matching_mode') or 'N/A'}",
                    f"Who left: {header.get('who_left_first') or 'N/A'}",
                    f"Tags: {tags}",
                ]
            )
        )

    def _update_prompt(self) -> None:
        header = self.current_header or {}
        compliance = str(header.get("compliance") or "")
        line_id = header.get("line_id")
        deviation_ply = header.get("deviation_ply_you")
        can_create_sideline = (
            compliance == "YOU_DEVIATED"
            and isinstance(deviation_ply, int)
            and deviation_ply > 0
        )
        if not can_create_sideline:
            self.prompt_line.setText(
                "Create sideline is available only for games with YOU_DEVIATED compliance."
            )
            self.prompt_move.setText("")
            self.create_sideline_button.setEnabled(False)
            return

        line_moves = self.controller.get_line_moves(line_id, deviation_ply) if line_id else []
        line_text = self._format_line_moves(line_moves)
        expected_move = line_moves[-1] if line_moves else None
        if expected_move:
            mover = "White" if deviation_ply % 2 == 1 else "Black"
            self.prompt_line.setText(f"Expected line to ply {deviation_ply}: {line_text}")
            self.prompt_move.setText(
                f"Expected {mover} move: {expected_move.get('san_move') or expected_move.get('uci_move')}"
            )
        elif line_id:
            self.prompt_line.setText("No repertoire move found for this deviation.")
            self.prompt_move.setText("")
        else:
            self.prompt_line.setText(
                f"Self deviation at ply {deviation_ply} detected; matched line is unavailable."
            )
            self.prompt_move.setText("")
        self.create_sideline_button.setEnabled(True)

    def _format_line_moves(self, moves: list[dict]) -> str:
        parts: list[str] = []
        for move in moves:
            ply = move.get("ply") or 0
            san = move.get("san_move") or move.get("uci_move") or ""
            if ply % 2 == 1:
                move_no = (ply + 1) // 2
                parts.append(f"{move_no}. {san}")
            else:
                parts.append(san)
        return " ".join(parts)

    def _on_move_selected(self, row: int, _column: int, _prev_row: int, _prev_col: int) -> None:
        if self._updating_selection:
            return
        if row < 0:
            return
        orientation = self._current_orientation()
        self.set_current_ply(row + 1, orientation)

    def set_current_ply(self, ply: int, orientation: chess.Color) -> None:
        ply = max(0, min(ply, len(self.moves)))
        self.current_ply = ply
        board = self.boards[ply] if ply < len(self.boards) else chess.Board()
        self.board_widget.set_position(board, orientation)

        eval_cp = None
        if ply == 0:
            self.eval_bar.set_eval(None)
        else:
            move = self.moves[ply - 1]
            eval_cp = move.get("post_eval_cp")
            self.eval_bar.set_eval(eval_cp)

        if ply == 0:
            self._updating_selection = True
            self.move_table.clearSelection()
            self._updating_selection = False
        else:
            self._updating_selection = True
            self.move_table.setCurrentCell(ply - 1, 0)
            self._updating_selection = False

    def _repertoire_eval_message(self, move: dict) -> str:
        if not self._should_show_rep_cpl_for_ply(move.get("ply")):
            return ""
        header = self.current_header or {}
        return repertoire_eval_message(
            move.get("your_cpl"),
            move.get("rep_cpl"),
            header.get("who_left_first"),
        )

    def _deviation_ply_for_rep_cpl(self) -> int | None:
        header = self.current_header or {}
        if str(header.get("compliance") or "") != "YOU_DEVIATED":
            return None
        deviation = header.get("deviation_ply_you")
        if not isinstance(deviation, int) or deviation <= 0:
            return None
        return deviation

    def _should_show_rep_cpl_for_ply(self, ply: int | None) -> bool:
        if not isinstance(ply, int):
            return False
        deviation = self._deviation_ply_for_rep_cpl()
        return deviation is not None and ply == deviation

    def _ensure_deviation_rep_cpl(self) -> None:
        game_id = self.current_game_id
        deviation_ply = self._deviation_ply_for_rep_cpl()
        if game_id is None or deviation_ply is None:
            return
        if deviation_ply < 1 or deviation_ply > len(self.moves):
            return
        if self.moves[deviation_ply - 1].get("rep_cpl") is not None:
            return

        key = (int(game_id), int(deviation_ply))
        if (
            self._rep_cpl_inflight == key
            and self._rep_cpl_worker
            and self._rep_cpl_worker.isRunning()
        ):
            return
        if self._rep_cpl_worker and self._rep_cpl_worker.isRunning():
            return

        self.status_label.setText("Computing Rep CPL...")
        worker = _RepCplWorker(self.controller, int(game_id), int(deviation_ply))
        worker.finished.connect(self._on_rep_cpl_finished)
        self._rep_cpl_inflight = key
        self._rep_cpl_worker = worker
        worker.start()

    def _on_rep_cpl_finished(self, payload: object) -> None:
        result = payload if isinstance(payload, dict) else {}
        game_id = int(result.get("game_id") or 0)
        ply = int(result.get("ply") or 0)
        success = bool(result.get("success"))
        rep_cpl = result.get("rep_cpl")
        message = str(result.get("message") or "")

        self._rep_cpl_inflight = None
        self._rep_cpl_worker = None
        if message:
            self.status_label.setText(message)
        if not success:
            return
        if self.current_game_id is None or int(self.current_game_id) != game_id:
            return
        if ply <= 0 or ply > len(self.moves):
            return

        self.moves[ply - 1]["rep_cpl"] = rep_cpl
        value = (
            f"{rep_cpl}"
            if self._should_show_rep_cpl_for_ply(ply) and rep_cpl is not None
            else ""
        )
        item = self.move_table.item(ply - 1, 5)
        if item is None:
            item = QtWidgets.QTableWidgetItem(value)
            self.move_table.setItem(ply - 1, 5, item)
        else:
            item.setText(value)

        if self.current_ply == ply:
            self.set_current_ply(self.current_ply, self._current_orientation())

    def _current_orientation(self) -> chess.Color:
        header = self.current_header or {}
        player_color = header.get("player_color") or "white"
        return chess.WHITE if player_color == "white" else chess.BLACK

    def _next_move(self) -> None:
        orientation = self._current_orientation()
        self.set_current_ply(self.current_ply + 1, orientation)

    def _prev_move(self) -> None:
        orientation = self._current_orientation()
        self.set_current_ply(self.current_ply - 1, orientation)

    def _go_start(self) -> None:
        orientation = self._current_orientation()
        self.set_current_ply(0, orientation)

    def _go_end(self) -> None:
        orientation = self._current_orientation()
        self.set_current_ply(len(self.moves), orientation)

    def _create_sideline_at_deviation(self) -> None:
        if self.current_game_id is None:
            self.status_label.setText("No game selected.")
            return
        success, message, item = self.controller.request_sideline_for_game_deviation(
            int(self.current_game_id)
        )
        if not success:
            self.status_label.setText(message)
            return
        request_count = int((item or {}).get("request_count") or 1)
        status = str((item or {}).get("status") or "PENDING")
        queue_key = str((item or {}).get("queue_key") or "")
        extra = f" [{status}]" if status else ""
        key_preview = f" ({queue_key[:10]})" if queue_key else ""
        self.status_label.setText(
            f"{message} Requests: {request_count}.{extra}{key_preview}"
        )

    def _reanalyze_game(self) -> None:
        if self.current_game_id is None:
            return
        self.status_label.setText("Reanalyzing...")
        self.reanalyze_button.setEnabled(False)

        worker = _ReanalysisWorker(self.controller, self.current_game_id)
        worker.finished.connect(self._on_reanalysis_done)
        worker.start()
        self._reanalysis_worker = worker

    def _on_reanalysis_done(self, success: bool, message: str) -> None:
        self.status_label.setText(message)
        self.reanalyze_button.setEnabled(True)
        if success and self.current_game_id is not None:
            self._load_game(self.current_game_id)

class _ReanalysisWorker(QtCore.QThread):
    finished = QtCore.Signal(bool, str)

    def __init__(self, controller, game_id: int) -> None:
        super().__init__()
        self.controller = controller
        self.game_id = game_id

    def run(self) -> None:
        try:
            self.controller.reanalyze_game(self.game_id)
            self.finished.emit(True, "Reanalysis complete")
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(False, str(exc))


class _RepCplWorker(QtCore.QThread):
    finished = QtCore.Signal(object)

    def __init__(self, controller, game_id: int, ply: int) -> None:
        super().__init__()
        self.controller = controller
        self.game_id = game_id
        self.ply = ply

    def run(self) -> None:
        result = self.controller.compute_deviation_rep_cpl(self.game_id, self.ply)
        payload = {
            "game_id": self.game_id,
            "ply": self.ply,
            "success": bool(result.get("success")),
            "rep_cpl": result.get("rep_cpl"),
            "message": result.get("message") or "",
        }
        self.finished.emit(payload)
