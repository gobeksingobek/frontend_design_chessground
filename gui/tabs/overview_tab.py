from __future__ import annotations

import math

from PySide6 import QtCore, QtWidgets


class AnalysisTaskWorker(QtCore.QThread):
    finished = QtCore.Signal(bool, str)
    progress = QtCore.Signal(dict)

    def __init__(self, controller, task_kind: str) -> None:
        super().__init__()
        self.controller = controller
        self.task_kind = task_kind

    def run(self) -> None:
        try:
            if self.task_kind == "analysis_run":
                self.controller.run_analysis(
                    reset_db=False,
                    progress_cb=lambda payload: self.progress.emit(payload),
                )
                self.finished.emit(True, "Analysis complete")
                return
            if self.task_kind == "analysis_full":
                self.controller.run_analysis(
                    reset_db=True,
                    progress_cb=lambda payload: self.progress.emit(payload),
                )
                self.finished.emit(True, "Full reanalysis complete")
                return
            if self.task_kind == "analysis_engine_only":
                self.controller.run_engine_analysis_only(
                    progress_cb=lambda payload: self.progress.emit(payload)
                )
                self.finished.emit(True, "Engine analysis complete")
                return
            if self.task_kind == "reanalyze_matching":
                self.controller.run_line_matching_reanalysis(
                    progress_cb=lambda payload: self.progress.emit(payload)
                )
                self.finished.emit(True, "Line matching reanalysis complete")
                return
            if self.task_kind == "reanalyze_game_details":
                self.controller.run_game_details_reanalysis(
                    progress_cb=lambda payload: self.progress.emit(payload)
                )
                self.finished.emit(True, "Game details reanalysis complete")
                return
            raise RuntimeError(f"Unknown task: {self.task_kind}")
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(False, str(exc))


class SmokeTestWorker(QtCore.QThread):
    finished = QtCore.Signal(bool, str, object)
    progress = QtCore.Signal(dict)

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

    def run(self) -> None:
        try:
            summary = self.controller.run_smoke_test(
                progress_cb=lambda payload: self.progress.emit(payload)
            )
            self.finished.emit(True, "Smoke test complete", summary)
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(False, str(exc), None)


class OverviewTab(QtWidgets.QWidget):
    analysis_completed = QtCore.Signal()

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.analysis_worker: AnalysisTaskWorker | None = None
        self.smoke_worker: SmokeTestWorker | None = None

        layout = QtWidgets.QVBoxLayout(self)

        self.summary_label = QtWidgets.QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.last_refresh_label = QtWidgets.QLabel("Last refresh: --")
        layout.addWidget(self.last_refresh_label)

        button_row = QtWidgets.QHBoxLayout()
        self.analysis_actions_button = QtWidgets.QToolButton()
        self.analysis_actions_button.setText("Analysis Actions")
        self.analysis_actions_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.analysis_menu = QtWidgets.QMenu(self.analysis_actions_button)

        analysis_menu = self.analysis_menu.addMenu("Analysis")
        self.action_run_analysis = analysis_menu.addAction("Run Analysis")
        self.action_run_engine_analysis = analysis_menu.addAction("Run Engine Analysis")

        reanalysis_menu = self.analysis_menu.addMenu("Reanalysis")
        self.action_full_reanalysis = reanalysis_menu.addAction(
            "Full reanalysis (overwrite DB)"
        )
        self.action_reanalyze_matching = reanalysis_menu.addAction(
            "Reanalyze line matching"
        )
        self.action_reanalyze_game_details = reanalysis_menu.addAction(
            "Reanalyze game details"
        )

        self.analysis_actions_button.setMenu(self.analysis_menu)

        self.run_smoke_button = QtWidgets.QPushButton("Run Smoke Test")
        self.refresh_button = QtWidgets.QPushButton("Refresh")

        button_row.addWidget(self.analysis_actions_button)
        button_row.addWidget(self.run_smoke_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.engine_scope_label = QtWidgets.QLabel(
            "Analysis Actions groups Run Analysis / Engine Analysis and Reanalysis tasks. "
            "Run Engine Analysis updates eval/cache and quality-derived views; "
            "it does not import/rematch games or refresh trainer auto-priority."
        )
        self.engine_scope_label.setWordWrap(True)
        layout.addWidget(self.engine_scope_label)

        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.action_run_analysis.triggered.connect(
            lambda: self._start_analysis_task("analysis_run", "Running analysis...")
        )
        self.action_run_engine_analysis.triggered.connect(
            lambda: self._start_analysis_task(
                "analysis_engine_only", "Running engine analysis..."
            )
        )
        self.action_full_reanalysis.triggered.connect(
            lambda: self._start_analysis_task(
                "analysis_full", "Running full reanalysis..."
            )
        )
        self.action_reanalyze_matching.triggered.connect(
            lambda: self._start_analysis_task(
                "reanalyze_matching", "Reanalyzing line matching..."
            )
        )
        self.action_reanalyze_game_details.triggered.connect(
            lambda: self._start_analysis_task(
                "reanalyze_game_details", "Reanalyzing game details..."
            )
        )
        self.run_smoke_button.clicked.connect(self._on_run_smoke_clicked)
        self.refresh_button.clicked.connect(self.refresh)

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
            (self.analysis_worker and self.analysis_worker.isRunning())
            or (self.smoke_worker and self.smoke_worker.isRunning())
            or self.controller.is_analysis_running()
        )

    def shutdown_workers(self, force: bool = True) -> None:
        self._set_analysis_controls_enabled(False)
        self._stop_thread(self.analysis_worker, force=force)
        self._stop_thread(self.smoke_worker, force=force)
        self.analysis_worker = None
        self.smoke_worker = None

    def refresh(self) -> None:
        self.summary_label.setText(self.controller.get_overview_summary())

    def set_last_refresh(self, ts_text: str) -> None:
        self.last_refresh_label.setText(f"Last refresh: {ts_text}")

    def _is_analysis_busy(self) -> bool:
        return (
            (self.analysis_worker and self.analysis_worker.isRunning())
            or (self.smoke_worker and self.smoke_worker.isRunning())
            or self.controller.is_analysis_running()
        )

    def _set_analysis_controls_enabled(self, enabled: bool) -> None:
        self.analysis_actions_button.setEnabled(enabled)
        self.run_smoke_button.setEnabled(enabled)

    def _start_analysis_task(self, task_kind: str, start_status: str) -> None:
        if self._is_analysis_busy():
            return
        self._set_analysis_controls_enabled(False)
        self.status_label.setText(start_status)
        self.analysis_worker = AnalysisTaskWorker(self.controller, task_kind)
        self.analysis_worker.finished.connect(self._on_analysis_task_finished)
        self.analysis_worker.progress.connect(self._on_progress)
        self.analysis_worker.start()

    def _on_run_smoke_clicked(self) -> None:
        if self._is_analysis_busy():
            return
        self._set_analysis_controls_enabled(False)
        self.status_label.setText("Running smoke test...")
        self.smoke_worker = SmokeTestWorker(self.controller)
        self.smoke_worker.finished.connect(self._on_smoke_worker_finished)
        self.smoke_worker.progress.connect(self._on_progress)
        self.smoke_worker.start()

    def _on_progress(self, payload: dict) -> None:
        self.status_label.setText(self._format_progress(payload))

    def _format_progress(self, payload: dict) -> str:
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
        return " | ".join(parts)

    def _on_analysis_task_finished(self, success: bool, message: str) -> None:
        self.status_label.setText(message)
        self._set_analysis_controls_enabled(True)
        if success:
            self.analysis_completed.emit()

    def _on_smoke_worker_finished(
        self,
        success: bool,
        message: str,
        summary: object,
    ) -> None:
        self.status_label.setText(message)
        self._set_analysis_controls_enabled(True)
        if not success:
            return
        info = self._format_smoke_summary(summary if isinstance(summary, dict) else {})
        QtWidgets.QMessageBox.information(self, "Smoke Test", info)

    def _format_smoke_summary(self, summary: dict) -> str:
        lines = [
            f"Smoke DB: {summary.get('smoke_db', 'N/A')}",
            f"Sample folder: {summary.get('smoke_root', 'N/A')}",
            f"Sampled repertoire games: {summary.get('repertoire_games_sampled', 0)}",
            f"Sampled input games: {summary.get('input_games_sampled', 0)}",
            (
                "Rows: "
                f"lines={summary.get('repertoire_lines', 0)}, "
                f"games={summary.get('games', 0)}, "
                f"matches={summary.get('matches', 0)}, "
                f"engine_cache={summary.get('engine_cache', 0)}, "
                f"analysis_ply={summary.get('analysis_ply', 0)}"
            ),
            f"DB size: {summary.get('db_size_mb', 0)} MB",
        ]
        return "\n".join(lines)
