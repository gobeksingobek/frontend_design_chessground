from __future__ import annotations

import configparser
from datetime import datetime
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from app_config import ensure_config_values, read_config_file, validate_app_config
from gui.tabs.games_tab import GamesTab
from gui.tabs.insights_tab import InsightsTab
from gui.tabs.lines_tab import LinesTab
from gui.tabs.overview_tab import OverviewTab
from gui.tabs.rating_bands_tab import RatingBandsTab
from gui.tabs.review_tab import ReviewTab
from gui.tabs.settings_tab import SettingsTab
from gui.tabs.time_tab import TimeTab
from gui.tabs.tree_tab import TreeTab
from gui.tabs.trainer_tab import TrainerTab
from gui.process_cleanup import terminate_child_processes_for_current_app
from gui.settings_editor import SettingsEditorDialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, controller, settings_path: Path) -> None:
        super().__init__()
        self.controller = controller
        self.settings_path = Path(settings_path)
        self.setWindowTitle("Repertoire Analyzer")
        self._closing = False
        self._shutdown_done = False

        self._build_menu()

        self.tabs = QtWidgets.QTabWidget()
        self.overview_tab = OverviewTab(controller)
        self.games_tab = GamesTab(controller)
        self.lines_tab = LinesTab(controller)
        self.tree_tab = TreeTab(controller)
        self.time_tab = TimeTab(controller)
        self.review_tab = ReviewTab(controller)
        self.rating_bands_tab = RatingBandsTab(controller)
        self.insights_tab = InsightsTab(controller)
        self.trainer_tab = TrainerTab(controller)
        self.settings_tab = SettingsTab(controller, self._open_settings_editor)

        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.games_tab, "Games")
        self.tabs.addTab(self.lines_tab, "Lines")
        self.tabs.addTab(self.tree_tab, "Tree")
        self.tabs.addTab(self.time_tab, "Time usage")
        self.tabs.addTab(self.rating_bands_tab, "Rating bands")
        self.tabs.addTab(self.insights_tab, "Insights")
        self.tabs.addTab(self.trainer_tab, "Trainer")
        self.tabs.addTab(self.review_tab, "Review")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.setCentralWidget(self.tabs)
        self.resize(1200, 700)

        self.overview_tab.analysis_completed.connect(self.refresh_all)
        self.games_tab.analysis_completed.connect(self.refresh_all)

    def refresh_all(self) -> None:
        self.overview_tab.refresh()
        self.games_tab.refresh()
        self.lines_tab.refresh()
        self.tree_tab.refresh()
        self.time_tab.refresh()
        self.rating_bands_tab.refresh()
        self.insights_tab.refresh()
        self.trainer_tab.update_ui()
        self.review_tab.refresh()
        self.settings_tab.refresh()
        self.overview_tab.set_last_refresh(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("Settings")
        edit_action = QtGui.QAction("Edit settings.ini...", self)
        edit_action.triggered.connect(self._open_settings_editor)
        settings_menu.addAction(edit_action)

    def _open_settings_editor(self) -> None:
        dialog = SettingsEditorDialog(self.settings_path, self._apply_settings, self)
        dialog.exec()

    def _apply_settings(self) -> tuple[bool, str]:
        try:
            config = read_config_file(self.settings_path)
        except configparser.Error as exc:
            message = f"Failed to parse settings.ini: {exc}"
            self.settings_tab.set_status(message)
            return False, message

        base_dir = self.settings_path.parent.parent
        app_config = ensure_config_values(config, base_dir)
        errors = validate_app_config(app_config)
        if errors:
            message = "Invalid settings: " + "; ".join(errors)
            self.settings_tab.set_status(message)
            return False, message

        try:
            self.controller.apply_config(app_config)
        except Exception as exc:  # pylint: disable=broad-except
            message = f"Failed to apply settings: {exc}"
            self.settings_tab.set_status(message)
            return False, message

        self.rating_bands_tab.set_band_size(app_config.rating_band_size)
        self.refresh_all()
        self.settings_tab.set_status("Settings applied.")
        return True, "Settings applied."

    def _has_active_background_work(self) -> bool:
        return bool(
            self.overview_tab.has_active_workers()
            or self.games_tab.has_active_workers()
            or self.controller.is_analysis_running()
        )

    def _shutdown_now(self, force: bool = True) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.overview_tab.shutdown_workers(force=force)
        self.games_tab.shutdown_workers(force=force)
        cleanup = terminate_child_processes_for_current_app()
        if cleanup.get("errors"):
            print("[shutdown cleanup warnings]", "; ".join(cleanup["errors"]))
        self.controller.close()

    def on_app_about_to_quit(self) -> None:
        self._shutdown_now(force=True)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self._closing:
            event.accept()
            return

        if self._has_active_background_work():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Force Stop Running Work",
                "Analysis/fetch/reanalyze is still running. Force stop and close?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return

        self._closing = True
        self._shutdown_now(force=True)
        event.accept()
