from __future__ import annotations

from pathlib import Path

import chess
from PySide6 import QtCore, QtGui, QtWidgets

from gui.widgets.board_widget import PngBoardWidget

DISCARD_PGN_PATH = Path(
    r"C:\Ahmet\test2\nf3_full_repertoire_by_first_black_move\filtered_bad_moves\discarded_filtered_lines\discarded.pgn"
)
AUTO_PLAY_DELAY_MS = 700
DEFAULT_STATUS_TEXT = "Learn ignores needs_review; needs_review affects Review selection."
TRAINER_SPLIT_LEFT = 3
TRAINER_SPLIT_RIGHT = 2


class TrainerTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.controller.ensure_trainer_sync()

        self.mode: str | None = None
        self.phase: str | None = None
        self.line_info: dict | None = None
        self.line_moves: list[dict] = []
        self.expected_move: str | None = None
        self.cursor_index = 0
        self.board = chess.Board()
        self.your_color = chess.WHITE
        self.waiting_for_input = False
        self.previewing = False
        self.current_attempts = 0
        self.mistake_in_phase = False
        self.auto_playing = False
        self._auto_queue: list[str] = []
        self._auto_token = 0
        self.completed_browse_enabled = False
        self.completed_boards: list[chess.Board] = []
        self.completed_ply = 0

        layout = QtWidgets.QHBoxLayout(self)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        self.board_widget = PngBoardWidget(self.controller.config.piece_dir, interactive=True)
        left_layout.addWidget(self.board_widget, 1)
        self.prompt_label = QtWidgets.QLabel("Trainer ready.")
        self.prompt_label.setWordWrap(True)
        prompt_height = int(self.prompt_label.fontMetrics().lineSpacing() * 2 + 6)
        self.prompt_label.setFixedHeight(prompt_height)
        left_layout.addWidget(self.prompt_label)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)

        self.learn_button = QtWidgets.QPushButton("Learn")
        self.review_button = QtWidgets.QPushButton("Review")
        self.restart_button = QtWidgets.QPushButton("Restart")
        self.priority_button = QtWidgets.QPushButton("Priority: Off")
        self.unmark_button = QtWidgets.QPushButton("Unmark Priority")
        self.discard_button = QtWidgets.QPushButton("Discard Line")
        self.restart_button.setEnabled(False)
        self.priority_button.setEnabled(False)
        self.unmark_button.setEnabled(False)
        self.discard_button.setEnabled(False)

        right_layout.addWidget(self.learn_button)
        right_layout.addWidget(self.review_button)
        right_layout.addWidget(self.restart_button)
        right_layout.addWidget(self.priority_button)
        right_layout.addWidget(self.unmark_button)
        right_layout.addWidget(self.discard_button)

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setText(DEFAULT_STATUS_TEXT)
        right_layout.addWidget(self.status_label)
        right_layout.addStretch()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, TRAINER_SPLIT_LEFT)
        splitter.setStretchFactor(1, TRAINER_SPLIT_RIGHT)
        QtCore.QTimer.singleShot(
            0,
            lambda: splitter.setSizes([TRAINER_SPLIT_LEFT, TRAINER_SPLIT_RIGHT]),
        )

        self.learn_button.clicked.connect(self.start_learn)
        self.review_button.clicked.connect(self.start_review)
        self.restart_button.clicked.connect(self.restart_current)
        self.priority_button.clicked.connect(self.toggle_priority)
        self.unmark_button.clicked.connect(self.unmark_priority)
        self.discard_button.clicked.connect(self.discard_line)
        self.board_widget.move_attempted.connect(self.on_move_attempted)
        QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Left),
            self,
            activated=self._browse_prev,
        )
        QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Right),
            self,
            activated=self._browse_next,
        )
        QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Up),
            self,
            activated=self._browse_start,
        )
        QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Down),
            self,
            activated=self._browse_end,
        )

        self.update_ui()

    def update_ui(self) -> None:
        if not self.line_info:
            self.info_label.setText("No line loaded.")
            self.priority_button.setEnabled(False)
            self.unmark_button.setEnabled(False)
            self.discard_button.setEnabled(False)
            return
        priority = self._effective_priority(self.line_info)
        side = self.line_info.get("side_to_play") or "white"
        override = self.line_info.get("priority_override")
        priority_text = "Yes" if priority else "No"
        if override == -1:
            priority_text = "No (ignored)"
        self.priority_button.setText("Priority: On" if priority else "Priority: Off")
        adaptive_cap = self.line_info.get("focus_max_ply")
        adaptive_text = (
            f"Adaptive cap: ply {int(adaptive_cap)}"
            if adaptive_cap is not None
            else "Adaptive cap: full line"
        )
        self.info_label.setText(
            " | ".join(
                [
                    f"Line: {self.line_info.get('line_id')}",
                    f"Side: {side}",
                    f"Mode: {self.mode or 'N/A'}",
                    f"Phase: {self.phase or 'N/A'}",
                    f"Priority: {priority_text}",
                    f"Auto-score: {int(self.line_info.get('auto_priority_score') or 0)}",
                    adaptive_text,
                ]
            )
        )
        self.priority_button.setEnabled(True)
        self.unmark_button.setEnabled(True)
        self.discard_button.setEnabled(self.mode == "learn")

    def start_learn(self) -> None:
        line_id = self.controller.select_next_trainer_line("learn")
        if not line_id:
            self.prompt_label.setText("No unlearned lines available.")
            return
        self._load_line(line_id)
        self.mode = "learn"
        self.phase = "guided"
        self.mistake_in_phase = False
        self._reset_board()
        self._advance_guided()
        self.restart_button.setEnabled(True)
        self.update_ui()

    def start_review(self) -> None:
        line_id = self.controller.select_next_trainer_line("review")
        if not line_id:
            self.prompt_label.setText("No learned lines to review yet.")
            return
        self._load_line(line_id)
        self.mode = "review"
        self.phase = "review"
        self.mistake_in_phase = False
        self._reset_board()
        self._advance_test_like()
        self.restart_button.setEnabled(True)
        self.update_ui()

    def restart_current(self) -> None:
        if not self.line_info:
            return
        if self.mode == "learn":
            self.phase = "guided"
        self.mistake_in_phase = False
        self._reset_board()
        if self.mode == "learn" and self.phase == "guided":
            self._advance_guided()
        else:
            self._advance_test_like()
        self.update_ui()

    def toggle_priority(self) -> None:
        if not self.line_info:
            return
        new_value = self.controller.toggle_trainer_priority(self.line_info["line_id"])
        self.line_info["priority_override"] = new_value
        self.update_ui()

    def unmark_priority(self) -> None:
        if not self.line_info:
            return
        self.controller.set_trainer_priority_override(self.line_info["line_id"], -1)
        self.line_info["priority_override"] = -1
        self.update_ui()

    def discard_line(self) -> None:
        if not self.line_info:
            return
        if self.mode != "learn":
            return
        self._auto_token += 1
        self.auto_playing = False
        self._auto_queue = []
        line_id = self.line_info["line_id"]
        reply = QtWidgets.QMessageBox.question(
            self,
            "Discard Variation",
            f"Discard line '{line_id}' and move it to discarded.pgn?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        ok, message = self.controller.discard_trainer_line(
            line_id, DISCARD_PGN_PATH
        )
        if not ok:
            self.prompt_label.setText(f"Discard failed: {message}")
            return
        self.line_info = None
        self.line_moves = []
        self.mode = None
        self.phase = None
        self.restart_button.setEnabled(False)
        self.prompt_label.setText("Line discarded. Choose Learn or Review.")
        self._reset_board()
        self.update_ui()

    def _load_line(self, line_id: str) -> None:
        info = self.controller.get_trainer_line(line_id)
        if not info:
            self.prompt_label.setText("Failed to load line.")
            return
        self.line_info = info
        self.line_moves = info.get("moves", [])
        focus_max = info.get("focus_max_ply")
        if focus_max:
            self.line_moves = self.line_moves[: int(focus_max)]
        side = info.get("side_to_play") or "white"
        self.your_color = chess.WHITE if side == "white" else chess.BLACK
        self.board_widget.set_position(self.board, self.your_color)

    def _reset_board(self) -> None:
        self.board = chess.Board()
        self.cursor_index = 0
        self.expected_move = None
        self.waiting_for_input = False
        self.previewing = False
        self.current_attempts = 0
        self.auto_playing = False
        self._auto_queue = []
        self._auto_token += 1
        self.completed_browse_enabled = False
        self.completed_boards = []
        self.completed_ply = 0
        self.status_label.setText(DEFAULT_STATUS_TEXT)
        self.board_widget.set_position(self.board, self.your_color)

    def _advance_guided(self) -> None:
        self.waiting_for_input = False
        self.previewing = False
        opponent_moves = self._collect_opponent_moves()
        self._schedule_auto_moves(opponent_moves, self._after_guided_opponent)

    def _after_guided_opponent(self) -> None:
        if self.cursor_index >= len(self.line_moves):
            self._start_test_phase()
            return
        self._start_preview()

    def _start_preview(self) -> None:
        self.expected_move = self._expected_move_uci()
        if not self.expected_move:
            self._start_test_phase()
            return
        self.prompt_label.setText("Observe the move, then repeat it.")
        QtCore.QTimer.singleShot(AUTO_PLAY_DELAY_MS, self._play_preview_move)

    def _play_preview_move(self) -> None:
        if not self.expected_move:
            return
        self._play_move(self.expected_move)
        self.previewing = True
        QtCore.QTimer.singleShot(AUTO_PLAY_DELAY_MS, self._end_preview)

    def _end_preview(self) -> None:
        if not self.previewing:
            return
        self.previewing = False
        if self.board.move_stack:
            self.board.pop()
        self.board_widget.set_position(self.board, self.your_color)
        self.waiting_for_input = True
        self.current_attempts = 0
        self.prompt_label.setText("Your move (repeat the shown move).")

    def _start_test_phase(self) -> None:
        self.phase = "test"
        self.mistake_in_phase = False
        self._reset_board()
        self._advance_test_like()
        self.update_ui()

    def _advance_test_like(self) -> None:
        if self.cursor_index >= len(self.line_moves):
            self._finish_line()
            return
        opponent_moves = self._collect_opponent_moves()
        self._schedule_auto_moves(opponent_moves, self._after_test_opponent)

    def _after_test_opponent(self) -> None:
        if self.cursor_index >= len(self.line_moves):
            self._finish_line()
            return
        self.expected_move = self._expected_move_uci()
        self.waiting_for_input = True
        self.current_attempts = 0
        self.prompt_label.setText("Your move.")

    def _collect_opponent_moves(self) -> list[str]:
        moves: list[str] = []
        temp_board = self.board.copy(stack=True)
        while self.cursor_index < len(self.line_moves) and temp_board.turn != self.your_color:
            move_uci = self._expected_move_uci()
            if not move_uci:
                break
            move = chess.Move.from_uci(move_uci)
            if move not in temp_board.legal_moves:
                break
            moves.append(move_uci)
            temp_board.push(move)
            self.cursor_index += 1
        return moves

    def _schedule_auto_moves(self, moves: list[str], on_done) -> None:
        if not moves:
            on_done()
            return
        self.auto_playing = True
        self._auto_queue = list(moves)
        self._auto_token += 1
        token = self._auto_token
        QtCore.QTimer.singleShot(
            AUTO_PLAY_DELAY_MS,
            lambda: self._auto_play_next(token, on_done),
        )

    def _auto_play_next(self, token: int, on_done) -> None:
        if token != self._auto_token:
            return
        if not self._auto_queue:
            self.auto_playing = False
            on_done()
            return
        move_uci = self._auto_queue.pop(0)
        self._play_move(move_uci)
        if not self._auto_queue:
            self.auto_playing = False
            on_done()
            return
        QtCore.QTimer.singleShot(
            AUTO_PLAY_DELAY_MS,
            lambda: self._auto_play_next(token, on_done),
        )

    def _expected_move_uci(self) -> str | None:
        if self.cursor_index >= len(self.line_moves):
            return None
        return self.line_moves[self.cursor_index].get("uci_move")

    def on_move_attempted(self, uci: str) -> None:
        if not self.waiting_for_input or self.previewing or self.auto_playing:
            return
        if not self.expected_move:
            return
        move = chess.Move.from_uci(uci)
        if move not in self.board.legal_moves:
            self._handle_incorrect("Illegal move. Try again.")
            return
        if uci == self.expected_move:
            self._handle_correct()
        else:
            self._handle_incorrect("Incorrect. Try again.")

    def _handle_correct(self) -> None:
        self.waiting_for_input = False
        self._play_move(self.expected_move)
        self.cursor_index += 1
        opponent_moves = self._collect_opponent_moves()
        if self.phase == "guided":
            self._schedule_auto_moves(opponent_moves, self._advance_guided)
        else:
            self._schedule_auto_moves(opponent_moves, self._advance_test_like)

    def _handle_incorrect(self, message: str) -> None:
        self.current_attempts += 1
        if self.current_attempts < 3:
            self.prompt_label.setText(f"{message} ({self.current_attempts}/3)")
            return
        self.prompt_label.setText("Showing correct move, then continue.")
        self.mistake_in_phase = True
        self.waiting_for_input = False
        QtCore.QTimer.singleShot(AUTO_PLAY_DELAY_MS, self._reveal_correct_move)

    def _reveal_correct_move(self) -> None:
        if not self.expected_move:
            return
        self._play_move(self.expected_move)
        self.cursor_index += 1
        opponent_moves = self._collect_opponent_moves()
        if self.phase == "guided":
            self._schedule_auto_moves(opponent_moves, self._advance_guided)
        else:
            self._schedule_auto_moves(opponent_moves, self._advance_test_like)

    def _play_move(self, uci: str) -> None:
        move = chess.Move.from_uci(uci)
        if move in self.board.legal_moves:
            self.board.push(move)
        self.board_widget.set_position(self.board, self.your_color)

    def _finish_line(self) -> None:
        if not self.line_info:
            return
        line_id = self.line_info["line_id"]
        streak = self.line_info.get("correct_streak") or 0
        if self.mistake_in_phase:
            new_streak = 0
            needs_review = 1
            times_incorrect = 1
            times_correct = 0
        else:
            new_streak = streak + 1
            needs_review = 0
            times_incorrect = 0
            times_correct = 1

        if self.mode == "learn" and self.phase == "test":
            self.controller.update_trainer_state(
                line_id,
                learned=1,
                needs_review=needs_review,
                correct_streak=new_streak,
                times_correct_delta=times_correct,
                times_incorrect_delta=times_incorrect,
            )
        elif self.mode == "review":
            self.controller.update_trainer_state(
                line_id,
                learned=1,
                needs_review=needs_review,
                correct_streak=new_streak,
                times_correct_delta=times_correct,
                times_incorrect_delta=times_incorrect,
            )
        elif self.mode == "learn" and self.phase == "guided":
            self._start_test_phase()
            return

        self.line_info["correct_streak"] = new_streak
        self.line_info["needs_review"] = needs_review
        self.line_info["learned"] = 1
        self.prompt_label.setText("Line complete. Press Learn or Review to continue.")
        self.waiting_for_input = False
        self._build_completed_boards()
        self.completed_browse_enabled = True
        self.update_ui()

    def _effective_priority(self, info: dict) -> bool:
        override = info.get("priority_override")
        if override == -1:
            return False
        if override == 1:
            return True
        return bool(info.get("is_priority"))

    def _build_completed_boards(self) -> None:
        board = chess.Board()
        boards = [board.copy(stack=True)]
        for move_row in self.line_moves:
            uci = move_row.get("uci_move")
            if not uci:
                continue
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                break
            board.push(move)
            boards.append(board.copy(stack=True))
        self.completed_boards = boards
        self.completed_ply = max(0, len(boards) - 1)
        self._apply_completed_ply()

    def _apply_completed_ply(self) -> None:
        if not self.completed_boards:
            return
        max_ply = len(self.completed_boards) - 1
        self.completed_ply = max(0, min(self.completed_ply, max_ply))
        self.board = self.completed_boards[self.completed_ply].copy(stack=True)
        self.board_widget.set_position(self.board, self.your_color)
        self.status_label.setText(f"Ply {self.completed_ply}/{max_ply}")
        self.prompt_label.setText(
            f"Line complete. Viewing ply {self.completed_ply}/{max_ply}. "
            "Press Learn or Review to continue."
        )

    def _browse_prev(self) -> None:
        if not self.completed_browse_enabled:
            return
        self.completed_ply -= 1
        self._apply_completed_ply()

    def _browse_next(self) -> None:
        if not self.completed_browse_enabled:
            return
        self.completed_ply += 1
        self._apply_completed_ply()

    def _browse_start(self) -> None:
        if not self.completed_browse_enabled:
            return
        self.completed_ply = 0
        self._apply_completed_ply()

    def _browse_end(self) -> None:
        if not self.completed_browse_enabled:
            return
        self.completed_ply = len(self.completed_boards) - 1
        self._apply_completed_ply()
