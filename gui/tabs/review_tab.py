from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ReviewTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self._current_proposition_id: int | None = None

        layout = QtWidgets.QVBoxLayout(self)
        control_row = QtWidgets.QHBoxLayout()
        control_row.addWidget(QtWidgets.QLabel("Status"))
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItem("Pending", "pending")
        self.status_filter.addItem("Approved", "approved")
        self.status_filter.addItem("Disapproved", "disapproved")
        self.status_filter.addItem("All", "all")
        control_row.addWidget(self.status_filter)
        control_row.addStretch()
        layout.addLayout(control_row)

        splitter = QtWidgets.QSplitter()
        layout.addWidget(splitter, 1)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Type", "Games", "Move", "Line Hint", "Updated"]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.table)

        detail_widget = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(detail_widget)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text, 1)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        detail_layout.addWidget(self.status_label)
        button_row = QtWidgets.QHBoxLayout()
        self.approve_button = QtWidgets.QPushButton("Approve")
        self.disapprove_button = QtWidgets.QPushButton("Disapprove")
        button_row.addWidget(self.approve_button)
        button_row.addWidget(self.disapprove_button)
        button_row.addStretch()
        detail_layout.addLayout(button_row)
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.table.currentCellChanged.connect(self._on_selection_changed)
        self.approve_button.clicked.connect(self._approve_selected)
        self.disapprove_button.clicked.connect(self._disapprove_selected)

        self.refresh()

    def refresh(self) -> None:
        rows = self.controller.get_review_propositions(
            status_filter=self._status_filter_value()
        )
        self.table.setRowCount(len(rows))
        selected_row = -1
        first_row = -1
        for row_index, item in enumerate(rows):
            proposition_id = int(item.get("id") or 0)
            if first_row < 0:
                first_row = row_index
            if (
                self._current_proposition_id is not None
                and proposition_id == self._current_proposition_id
            ):
                selected_row = row_index
            values = [
                item.get("status") or "",
                item.get("proposition_type") or "",
                str(item.get("evidence_count") or 0),
                item.get("uci_move") or "",
                item.get("line_id_hint") or "",
                item.get("updated_at") or "",
            ]
            for col_index, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(value)
                if col_index == 0:
                    cell.setData(QtCore.Qt.UserRole, proposition_id)
                self.table.setItem(row_index, col_index, cell)

        if selected_row < 0:
            selected_row = first_row
        if selected_row >= 0:
            self.table.setCurrentCell(selected_row, 0)
            self._load_selected_detail(selected_row)
        else:
            self._current_proposition_id = None
            self.detail_text.setPlainText("No propositions.")
            self.status_label.setText("")
            self.approve_button.setEnabled(False)
            self.disapprove_button.setEnabled(False)

    def _status_filter_value(self) -> str:
        return str(self.status_filter.currentData() or "pending")

    def _on_selection_changed(
        self,
        row: int,
        _column: int,
        _prev_row: int,
        _prev_col: int,
    ) -> None:
        self._load_selected_detail(row)

    def _selected_proposition_id(self, row: int) -> int | None:
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        proposition_id = item.data(QtCore.Qt.UserRole)
        if proposition_id is None:
            return None
        return int(proposition_id)

    def _load_selected_detail(self, row: int) -> None:
        proposition_id = self._selected_proposition_id(row)
        if proposition_id is None:
            self._current_proposition_id = None
            self.detail_text.setPlainText("No proposition selected.")
            self.approve_button.setEnabled(False)
            self.disapprove_button.setEnabled(False)
            return

        detail = self.controller.get_review_proposition_detail(proposition_id)
        if not detail:
            self._current_proposition_id = None
            self.detail_text.setPlainText("Proposition not found.")
            self.approve_button.setEnabled(False)
            self.disapprove_button.setEnabled(False)
            return

        self._current_proposition_id = proposition_id
        lines = [
            f"ID: {detail.get('id')}",
            f"Type: {detail.get('proposition_type')}",
            f"Status: {detail.get('status')}",
            f"Evidence: {detail.get('evidence_count')} (threshold: >{detail.get('threshold_count')})",
            f"Position ID: {detail.get('pos_id')}",
            f"Opponent move: {detail.get('uci_move')}",
            f"Line hint: {detail.get('line_id_hint') or 'N/A'}",
        ]
        detail_payload = detail.get("detail") if isinstance(detail.get("detail"), dict) else {}
        fen = detail_payload.get("fen")
        if fen:
            lines.append(f"FEN: {fen}")

        sample_games = detail_payload.get("sample_games")
        if isinstance(sample_games, list) and sample_games:
            lines.append("")
            lines.append("Sample games:")
            for sample in sample_games:
                if not isinstance(sample, dict):
                    continue
                lines.append(
                    " - "
                    f"#{sample.get('game_id')} "
                    f"{sample.get('date') or ''} "
                    f"{sample.get('white') or ''} vs {sample.get('black') or ''} "
                    f"{sample.get('result') or ''} "
                    f"(opp deviation ply {sample.get('deviation_ply_opp')})"
                )

        self.detail_text.setPlainText("\n".join(lines))
        self.status_label.setText("")
        status = str(detail.get("status") or "").upper()
        self.approve_button.setEnabled(status != "APPROVED")
        self.disapprove_button.setEnabled(status != "DISAPPROVED")

    def _approve_selected(self) -> None:
        if self._current_proposition_id is None:
            return
        success, message = self.controller.approve_review_proposition(
            self._current_proposition_id
        )
        self.status_label.setText(message)
        if success:
            self.refresh()

    def _disapprove_selected(self) -> None:
        if self._current_proposition_id is None:
            return
        success, message = self.controller.disapprove_review_proposition(
            self._current_proposition_id
        )
        self.status_label.setText(message)
        if success:
            self.refresh()
