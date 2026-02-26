from __future__ import annotations

from PySide6 import QtWidgets


class InsightsTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        layout = QtWidgets.QVBoxLayout(self)

        button_row = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Category", "Title", "Details"])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.refresh_button.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        insights = self.controller.get_insights()
        self.table.setRowCount(len(insights))
        for row_index, insight in enumerate(insights):
            values = [
                insight.get("category") or "",
                insight.get("title") or "",
                insight.get("details") or "",
            ]
            for col_index, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(value)
                self.table.setItem(row_index, col_index, cell)
