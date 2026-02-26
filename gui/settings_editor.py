from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets


class SettingsEditorDialog(QtWidgets.QDialog):
    def __init__(
        self,
        settings_path: Path,
        apply_callback=None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_path = Path(settings_path)
        self.apply_callback = apply_callback
        self.setWindowTitle("Edit settings.ini")
        self.resize(700, 500)

        layout = QtWidgets.QVBoxLayout(self)

        self.path_label = QtWidgets.QLabel(f"File: {self.settings_path}")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        layout.addWidget(self.editor)

        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        button_row = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save + Apply")
        self.reload_button = QtWidgets.QPushButton("Reload")
        self.close_button = QtWidgets.QPushButton("Close")
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.reload_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.save_button.clicked.connect(self._save_file)
        self.reload_button.clicked.connect(self._load_file)
        self.close_button.clicked.connect(self.accept)

        self._load_file()

    def _load_file(self) -> None:
        try:
            if self.settings_path.exists():
                content = self.settings_path.read_text(encoding="utf-8", errors="replace")
            else:
                content = ""
            self.editor.setPlainText(content)
            self.status_label.setText("")
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Settings", f"Failed to read file: {exc}")

    def _save_file(self) -> None:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(self.editor.toPlainText(), encoding="utf-8")
            if self.apply_callback:
                success, message = self.apply_callback()
                if not success:
                    QtWidgets.QMessageBox.warning(self, "Settings", message)
                self.status_label.setText(message)
            else:
                self.status_label.setText("Saved.")
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Settings", f"Failed to save file: {exc}")
