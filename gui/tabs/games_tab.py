from __future__ import annotations

import math

from PySide6 import QtCore, QtWidgets

from gui.tabs.game_details_tab import GameDetailsTab


class FetchWorker(QtCore.QThread):
    finished = QtCore.Signal(object)

    def __init__(self, controller, variants: list[str]) -> None:
        super().__init__()
        self.controller = controller
        self.variants = variants

    def run(self) -> None:
        try:
            result = self.controller.fetch_games(self.variants)
            self.finished.emit(result)
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(
                {
                    "success": False,
                    "message": str(exc),
                    "total_new_games": 0,
                    "total_seen_games": 0,
                    "had_source_errors": True,
                }
            )


class AutoAnalysisWorker(QtCore.QThread):
    finished = QtCore.Signal(bool, str)
    progress = QtCore.Signal(dict)

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

    def run(self) -> None:
        try:
            self.controller.run_analysis(
                reset_db=False,
                progress_cb=lambda payload: self.progress.emit(payload),
            )
            self.finished.emit(True, "Analysis complete")
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(False, str(exc))


class GamesTab(QtWidgets.QWidget):
    analysis_completed = QtCore.Signal()

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self._last_selected_game_id: int | None = None
        self._last_scroll_value = 0
        self._row_by_game_id: dict[int, int] = {}
        self.fetch_worker: FetchWorker | None = None
        self.analysis_worker: AutoAnalysisWorker | None = None
        self._pending_auto_analysis = False
        self._pending_auto_new_games = 0

        layout = QtWidgets.QVBoxLayout(self)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack)

        self.list_page = QtWidgets.QWidget()
        list_layout = QtWidgets.QVBoxLayout(self.list_page)

        self.fetch_button = QtWidgets.QPushButton("Fetch Games")
        list_layout.addWidget(self.fetch_button)

        self.variants_button = QtWidgets.QToolButton()
        self.variants_button.setText("Variants")
        self.variants_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.variants_menu = QtWidgets.QMenu(self.variants_button)
        self.variant_actions: dict[str, object] = {}
        for key, label in (("blitz", "Blitz"), ("rapid", "Rapid"), ("daily", "Daily")):
            action = self.variants_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(True)
            self.variant_actions[key] = action
        self.variants_button.setMenu(self.variants_menu)
        list_layout.addWidget(self.variants_button)

        self.fetch_status_label = QtWidgets.QLabel("Idle")
        self.fetch_status_label.setWordWrap(True)
        list_layout.addWidget(self.fetch_status_label)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels(
            [
                "Date",
                "White",
                "Black",
                "Result",
                "White Elo",
                "Black Elo",
                "Time Control",
                "Line ID",
                "Compliance",
                "Max Ply",
                "Match Mode",
                "Who Left",
                "Rep (Main/Other/Out)",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(
            lambda item: self._open_selected_game_from_row(item.row())
        )
        self.table.itemActivated.connect(
            lambda item: self._open_selected_game_from_row(item.row())
        )
        list_layout.addWidget(self.table)

        self.details_page = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(self.details_page)
        top_row = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.clicked.connect(self._on_back_clicked)
        top_row.addWidget(self.back_button)
        top_row.addStretch()
        details_layout.addLayout(top_row)
        self.details_tab = GameDetailsTab(controller, show_game_selector=False)
        details_layout.addWidget(self.details_tab)

        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.details_page)
        self.stack.setCurrentWidget(self.list_page)

        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self._queue_poll_timer = QtCore.QTimer(self)
        self._queue_poll_timer.setInterval(1000)
        self._queue_poll_timer.timeout.connect(self._drain_pending_auto_analysis)
        self._queue_poll_timer.start()

        self._apply_fetch_settings()
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
            (self.fetch_worker and self.fetch_worker.isRunning())
            or (self.analysis_worker and self.analysis_worker.isRunning())
            or self.details_tab.has_active_workers()
            or self.controller.is_analysis_running()
        )

    def shutdown_workers(self, force: bool = True) -> None:
        self.fetch_button.setEnabled(False)
        if self._queue_poll_timer.isActive():
            self._queue_poll_timer.stop()
        self._pending_auto_analysis = False
        self._pending_auto_new_games = 0
        self._stop_thread(self.fetch_worker, force=force)
        self._stop_thread(self.analysis_worker, force=force)
        self.fetch_worker = None
        self.analysis_worker = None
        self.details_tab.shutdown_workers(force=force)

    def _apply_fetch_settings(self) -> None:
        selected = {v.lower() for v in (self.controller.config.fetch_variants or [])}
        if not selected:
            selected = {"blitz", "rapid", "daily"}
        for key, action in self.variant_actions.items():
            action.setChecked(key in selected)

    def refresh(self) -> None:
        self._apply_fetch_settings()
        games = self.controller.get_game_overview()
        self._row_by_game_id = {}
        self.table.setRowCount(len(games))

        for row_index, game in enumerate(games):
            game_id = game.get("id")
            if game_id is not None:
                self._row_by_game_id[int(game_id)] = row_index
            rep_main = game.get("in_main") or 0
            rep_other = game.get("in_other") or 0
            rep_out = game.get("out_rep") or 0
            rep_summary = f"{rep_main}/{rep_other}/{rep_out}"
            values = [
                game.get("date") or "",
                game.get("white") or "",
                game.get("black") or "",
                game.get("result") or "",
                str(game.get("white_elo") or ""),
                str(game.get("black_elo") or ""),
                game.get("time_control") or "",
                game.get("line_id") or "",
                game.get("compliance") or "",
                str(game.get("max_matched_ply") or ""),
                game.get("matching_mode") or "",
                game.get("who_left_first") or "",
                rep_summary,
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if game_id is not None:
                    item.setData(QtCore.Qt.UserRole, int(game_id))
                self.table.setItem(row_index, col_index, item)

        if self.stack.currentWidget() is self.details_page:
            current_id = self.details_tab.current_game_id
            if current_id is None or not self.details_tab.load_game_by_id(current_id):
                self._on_back_clicked()
        self._drain_pending_auto_analysis()

    def _selected_fetch_variants(self) -> list[str]:
        return [
            key
            for key, action in self.variant_actions.items()
            if action.isChecked()
        ]

    def _is_analysis_busy(self) -> bool:
        return (
            (self.analysis_worker and self.analysis_worker.isRunning())
            or self.controller.is_analysis_running()
        )

    def _on_fetch_clicked(self) -> None:
        if self.fetch_worker and self.fetch_worker.isRunning():
            return
        variants = self._selected_fetch_variants()
        if not variants:
            self.fetch_status_label.setText(
                "Select at least one variant (Blitz, Rapid, Daily)."
            )
            return
        self.fetch_button.setEnabled(False)
        self.fetch_status_label.setText("Fetching games...")
        self.fetch_worker = FetchWorker(self.controller, variants)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.start()

    def _on_fetch_finished(self, payload: object) -> None:
        result = payload if isinstance(payload, dict) else {}
        message = str(result.get("message") or "Fetch completed.")
        total_new_games = int(result.get("total_new_games") or 0)
        self.fetch_button.setEnabled(True)
        self.fetch_status_label.setText(message)

        if total_new_games <= 0:
            return
        if self._is_analysis_busy():
            self._pending_auto_analysis = True
            self._pending_auto_new_games += total_new_games
            self.fetch_status_label.setText(
                f"{message} | Fetched {total_new_games} new games. Analysis queued (busy)."
            )
            return

        self.fetch_status_label.setText(
            f"{message} | Fetched {total_new_games} new games. Starting analysis..."
        )
        self._start_auto_analysis()

    def _start_auto_analysis(self) -> None:
        if self._is_analysis_busy():
            return
        self.analysis_worker = AutoAnalysisWorker(self.controller)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _on_analysis_progress(self, payload: dict) -> None:
        phase = payload.get("phase") or "Working"
        done = payload.get("done")
        total = payload.get("total")
        speed = payload.get("speed")
        eta_seconds = payload.get("eta_seconds")

        parts = [str(phase)]
        if isinstance(done, (int, float)) and isinstance(total, (int, float)):
            if total > 0:
                parts.append(f"{int(done)}/{int(total)}")
            else:
                parts.append(f"{int(done)}")
        if isinstance(speed, (int, float)) and speed > 0:
            parts.append(f"{speed:.1f} pos/s")
        if isinstance(eta_seconds, (int, float)) and eta_seconds > 0:
            eta = int(math.ceil(float(eta_seconds)))
            minutes = eta // 60
            seconds = eta % 60
            parts.append(f"ETA {minutes:02d}:{seconds:02d}")
        self.fetch_status_label.setText(" | ".join(parts))

    def _on_analysis_finished(self, success: bool, message: str) -> None:
        self.fetch_status_label.setText(message)
        if success:
            self.analysis_completed.emit()
        self._drain_pending_auto_analysis()

    def _drain_pending_auto_analysis(self) -> None:
        if not self._pending_auto_analysis:
            return
        if self._is_analysis_busy():
            return
        queued_new = self._pending_auto_new_games
        self._pending_auto_analysis = False
        self._pending_auto_new_games = 0
        self.fetch_status_label.setText(
            f"Fetched {queued_new} new games. Starting queued analysis..."
        )
        self._start_auto_analysis()

    def _game_id_for_row(self, row: int) -> int | None:
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        game_id = item.data(QtCore.Qt.UserRole)
        if game_id is None:
            return None
        return int(game_id)

    def _open_selected_game_from_row(self, row: int) -> None:
        game_id = self._game_id_for_row(row)
        if game_id is None:
            return
        self._last_selected_game_id = game_id
        self._last_scroll_value = self.table.verticalScrollBar().value()
        if not self.details_tab.load_game_by_id(game_id):
            return
        self.stack.setCurrentWidget(self.details_page)

    def _on_back_clicked(self) -> None:
        self.stack.setCurrentWidget(self.list_page)
        self._restore_list_state()

    def _restore_list_state(self) -> None:
        def _apply() -> None:
            row = None
            if self._last_selected_game_id is not None:
                row = self._row_by_game_id.get(self._last_selected_game_id)
            if row is not None and row >= 0:
                self.table.setCurrentCell(row, 0)
                self.table.selectRow(row)
            scroll = self.table.verticalScrollBar()
            clamped = max(scroll.minimum(), min(self._last_scroll_value, scroll.maximum()))
            scroll.setValue(clamped)

        QtCore.QTimer.singleShot(0, _apply)
