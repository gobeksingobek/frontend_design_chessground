from __future__ import annotations

from PySide6 import QtWidgets


class TimeTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Month",
                "Games",
                "Avg In-Book (s)",
                "Avg Out-of-Book (s)",
                "Avg In-Book %",
                "Avg Out-of-Book %",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.pattern_label = QtWidgets.QLabel()
        self.pattern_label.setWordWrap(True)
        layout.addWidget(self.pattern_label)

        note = QtWidgets.QLabel("Daily games are excluded from time usage statistics.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.refresh()

    def refresh(self) -> None:
        stats = self.controller.get_month_stats()
        self.table.setRowCount(len(stats))

        for row_index, entry in enumerate(stats):
            month = entry.get("key") or ""
            in_book = entry.get("in_book_avg")
            out_book = entry.get("out_book_avg")
            in_frac = entry.get("in_book_frac_avg")
            out_frac = entry.get("out_book_frac_avg")
            values = [
                month,
                str(entry.get("total_games") or 0),
                f"{in_book:.1f}" if in_book is not None else "",
                f"{out_book:.1f}" if out_book is not None else "",
                f"{(in_frac or 0) * 100:.1f}%" if in_frac is not None else "",
                f"{(out_frac or 0) * 100:.1f}%" if out_frac is not None else "",
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                self.table.setItem(row_index, col_index, item)

        patterns = self.controller.get_time_pattern_summary()
        if patterns:
            self.pattern_label.setText(
                "Patterns: "
                f"slow in-book {patterns.get('slow_in_book', 0)} | "
                f"instant out-of-book {patterns.get('instant_out_of_book', 0)} | "
                f"blunder cluster {patterns.get('blunder_cluster', 0)}"
            )
        else:
            self.pattern_label.setText("")
