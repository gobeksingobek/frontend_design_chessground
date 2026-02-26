from __future__ import annotations

from PySide6 import QtWidgets


class LinesTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "Line ID",
                "Games",
                "Compliance Rate",
                "Avg Dev Ply",
                "Wins",
                "Losses",
                "Draws",
                "Avg Eval Exit",
                "In-Rep Other %",
                "Opp Dev Known %",
                "Time In/Out",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        stats = self.controller.get_line_stats()
        self.table.setRowCount(len(stats))

        for row_index, entry in enumerate(stats):
            line_id = entry.get("key") or ""
            compliance_rate = entry.get("compliance_rate")
            avg_dev = entry.get("avg_deviation_ply")
            avg_eval = entry.get("avg_eval_exit")
            in_rep_other_rate = entry.get("in_rep_other_rate")
            opp_known_rate = entry.get("opp_dev_known_rate")
            in_book = entry.get("in_book_avg")
            out_book = entry.get("out_book_avg")
            time_text = ""
            if in_book is not None or out_book is not None:
                time_text = f"{in_book or 0:.1f}s / {out_book or 0:.1f}s"

            values = [
                line_id,
                str(entry.get("total_games") or 0),
                f"{(compliance_rate or 0) * 100:.1f}%" if compliance_rate is not None else "",
                f"{avg_dev:.1f}" if avg_dev is not None else "",
                str(entry.get("wins") or 0),
                str(entry.get("losses") or 0),
                str(entry.get("draws") or 0),
                f"{avg_eval:.1f}" if avg_eval is not None else "",
                f"{(in_rep_other_rate or 0) * 100:.1f}%" if in_rep_other_rate is not None else "",
                f"{(opp_known_rate or 0) * 100:.1f}%" if opp_known_rate is not None else "",
                time_text,
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                self.table.setItem(row_index, col_index, item)
