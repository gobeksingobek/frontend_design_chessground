from __future__ import annotations

from PySide6 import QtWidgets


class SettingsTab(QtWidgets.QWidget):
    def __init__(self, controller, open_settings_editor) -> None:
        super().__init__()
        self.controller = controller
        self._open_settings_editor = open_settings_editor

        layout = QtWidgets.QVBoxLayout(self)

        self.config_label = QtWidgets.QLabel("")
        self.config_label.setWordWrap(True)
        layout.addWidget(self.config_label)

        button_row = QtWidgets.QHBoxLayout()
        self.edit_button = QtWidgets.QPushButton("Edit settings.ini...")
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.refresh_button.clicked.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        self.config_label.setText(self.controller.get_path_summary())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text or "")

    def _on_edit_clicked(self) -> None:
        self._open_settings_editor()
