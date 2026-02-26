from __future__ import annotations

from PySide6 import QtWidgets


class RatingBandsTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        layout = QtWidgets.QVBoxLayout(self)

        control_row = QtWidgets.QHBoxLayout()
        control_row.addWidget(QtWidgets.QLabel("Band size"))
        self.band_spin = QtWidgets.QSpinBox()
        self.band_spin.setRange(1, 1000)
        self.band_spin.setValue(self.controller.config.rating_band_size)
        control_row.addWidget(self.band_spin)
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        control_row.addWidget(self.refresh_button)
        control_row.addStretch()
        layout.addLayout(control_row)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "White Band",
                "Black Band",
                "Games",
                "Compliance Rate",
                "Avg Dev Ply",
                "Wins",
                "Losses",
                "Draws",
                "Avg Eval Exit",
                "Time In/Out",
                "Time In/Out %",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.band_spin.valueChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)

        self.refresh()

    def set_band_size(self, value: int) -> None:
        self.band_spin.setValue(value)

    def refresh(self) -> None:
        band_size = int(self.band_spin.value())
        stats = self.controller.get_rating_band_stats(band_size)
        self.table.setRowCount(len(stats))

        for row_index, entry in enumerate(stats):
            compliance_rate = entry.get("compliance_rate")
            avg_dev = entry.get("avg_deviation_ply")
            avg_eval = entry.get("avg_eval_exit")
            in_book = entry.get("in_book_avg")
            out_book = entry.get("out_book_avg")
            in_frac = entry.get("in_book_frac_avg")
            out_frac = entry.get("out_book_frac_avg")
            time_text = ""
            if in_book is not None or out_book is not None:
                time_text = f"{in_book or 0:.1f}s / {out_book or 0:.1f}s"
            frac_text = ""
            if in_frac is not None or out_frac is not None:
                frac_text = f"{(in_frac or 0) * 100:.1f}% / {(out_frac or 0) * 100:.1f}%"

            values = [
                entry.get("white_band") or "",
                entry.get("black_band") or "",
                str(entry.get("total_games") or 0),
                f"{(compliance_rate or 0) * 100:.1f}%" if compliance_rate is not None else "",
                f"{avg_dev:.1f}" if avg_dev is not None else "",
                str(entry.get("wins") or 0),
                str(entry.get("losses") or 0),
                str(entry.get("draws") or 0),
                f"{avg_eval:.1f}" if avg_eval is not None else "",
                time_text,
                frac_text,
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                self.table.setItem(row_index, col_index, item)
