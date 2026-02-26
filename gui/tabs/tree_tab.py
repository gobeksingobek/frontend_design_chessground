from __future__ import annotations

from datetime import date

import chess
from PySide6 import QtCore, QtGui, QtWidgets

from analysis.position_utils import normalize_fen
from gui.widgets.board_widget import PngBoardWidget


class TreeTab(QtWidgets.QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller

        layout = QtWidgets.QVBoxLayout(self)
        self.subtabs = QtWidgets.QTabWidget()
        self.repertoire_pane = _TreePane(controller, mode="repertoire")
        self.game_pane = _TreePane(controller, mode="game")
        self.subtabs.addTab(self.repertoire_pane, "Repertoire")
        self.subtabs.addTab(self.game_pane, "Game")
        layout.addWidget(self.subtabs)

    def refresh(self) -> None:
        self.repertoire_pane.refresh()
        self.game_pane.refresh()


class _TreePane(QtWidgets.QWidget):
    def __init__(self, controller, mode: str) -> None:
        super().__init__()
        self.controller = controller
        self.mode = mode
        self.board = chess.Board()
        self.path_uci: list[str] = []
        self.rows: list[dict] = []

        layout = QtWidgets.QVBoxLayout(self)

        if self.mode == "game":
            filter_row = QtWidgets.QHBoxLayout()
            filter_row.addWidget(QtWidgets.QLabel("From"))
            self.date_from_edit = QtWidgets.QDateEdit()
            self.date_from_edit.setCalendarPopup(True)
            self.date_from_edit.setDisplayFormat("yyyy-MM-dd")
            self.date_from_edit.setDate(QtCore.QDate(1900, 1, 1))
            filter_row.addWidget(self.date_from_edit)

            filter_row.addWidget(QtWidgets.QLabel("To"))
            self.date_to_edit = QtWidgets.QDateEdit()
            self.date_to_edit.setCalendarPopup(True)
            self.date_to_edit.setDisplayFormat("yyyy-MM-dd")
            today = date.today()
            self.date_to_edit.setDate(QtCore.QDate(today.year, today.month, today.day))
            filter_row.addWidget(self.date_to_edit)

            filter_row.addWidget(QtWidgets.QLabel("Time"))
            self.time_class_combo = QtWidgets.QComboBox()
            self.time_class_combo.addItem("All", "all")
            self.time_class_combo.addItem("Bullet", "bullet")
            self.time_class_combo.addItem("Blitz", "blitz")
            self.time_class_combo.addItem("Rapid", "rapid")
            self.time_class_combo.addItem("Daily", "daily")
            self.time_class_combo.addItem("Other", "other")
            filter_row.addWidget(self.time_class_combo)

            filter_row.addWidget(QtWidgets.QLabel("Opp Elo Min"))
            self.opp_elo_min = QtWidgets.QSpinBox()
            self.opp_elo_min.setRange(0, 4000)
            self.opp_elo_min.setSpecialValueText("Any")
            filter_row.addWidget(self.opp_elo_min)

            filter_row.addWidget(QtWidgets.QLabel("Opp Elo Max"))
            self.opp_elo_max = QtWidgets.QSpinBox()
            self.opp_elo_max.setRange(0, 4000)
            self.opp_elo_max.setSpecialValueText("Any")
            filter_row.addWidget(self.opp_elo_max)

            self.apply_filters_button = QtWidgets.QPushButton("Apply")
            filter_row.addWidget(self.apply_filters_button)
            filter_row.addStretch()
            layout.addLayout(filter_row)
            self.apply_filters_button.clicked.connect(self._reload_current_node)
        else:
            self.date_from_edit = None
            self.date_to_edit = None
            self.time_class_combo = None
            self.opp_elo_min = None
            self.opp_elo_max = None
            self.apply_filters_button = None

        nav_row = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("Back")
        self.root_button = QtWidgets.QPushButton("Root")
        nav_row.addWidget(self.back_button)
        nav_row.addWidget(self.root_button)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        self.path_label = QtWidgets.QLabel("Path: (root)")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        self.board_widget = PngBoardWidget(self.controller.config.piece_dir)
        left_layout.addWidget(self.board_widget, 1)
        splitter.addWidget(left_widget)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        if self.mode == "repertoire":
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(
                ["Move", "Weight", "Priority", "Mainline"]
            )
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["Move", "Games", "W/D/L", "Score %", "Avg Opp Elo"]
            )
        right_layout.addWidget(self.table, 1)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self.back_button.clicked.connect(self._go_back)
        self.root_button.clicked.connect(self._go_root)
        self.table.itemDoubleClicked.connect(self._on_move_activated)
        self.table.itemActivated.connect(self._on_move_activated)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self, activated=self._go_back)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Backspace), self, activated=self._go_back)

        self._reload_current_node()

    def refresh(self) -> None:
        self._reload_current_node()

    def _go_back(self) -> None:
        if not self.path_uci:
            return
        self.path_uci.pop()
        if self.board.move_stack:
            self.board.pop()
        self._reload_current_node()

    def _go_root(self) -> None:
        self.path_uci = []
        self.board = chess.Board()
        self._reload_current_node()

    def _on_move_activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item is None:
            return
        row = item.row()
        if row < 0:
            return
        first_item = self.table.item(row, 0)
        if first_item is None:
            return
        payload = first_item.data(QtCore.Qt.UserRole)
        if not isinstance(payload, dict):
            return
        uci_move = payload.get("uci_move")
        if not uci_move:
            return
        try:
            move = chess.Move.from_uci(str(uci_move))
        except ValueError:
            self.status_label.setText(f"Invalid move: {uci_move}")
            return
        if move not in self.board.legal_moves:
            self.status_label.setText(f"Illegal from current position: {uci_move}")
            return
        self.board.push(move)
        self.path_uci.append(str(uci_move))
        self._reload_current_node()

    def _reload_current_node(self) -> None:
        self.board_widget.set_position(self.board, chess.WHITE)
        self.path_label.setText(f"Path: {self._path_text()}")
        pos_id = self._current_pos_id()
        if pos_id is None:
            self.rows = []
            self.table.setRowCount(0)
            self.status_label.setText("Current position is not indexed.")
            return

        self.status_label.setText("")
        if self.mode == "repertoire":
            rows = self.controller.get_tree_repertoire_children(pos_id, my_side_only=True)
            if not rows:
                fallback = self.controller.get_tree_repertoire_children(
                    pos_id, my_side_only=False
                )
                if fallback:
                    self.status_label.setText(
                        "No my-side repertoire moves here; showing all continuations."
                    )
                    rows = fallback
                else:
                    self.status_label.setText("No repertoire moves from this position.")
            self.rows = rows
            self._populate_repertoire_table(rows)
            return

        date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to = self.date_to_edit.date().toString("yyyy-MM-dd")
        time_class = str(self.time_class_combo.currentData() or "all")
        elo_min = int(self.opp_elo_min.value()) if self.opp_elo_min else 0
        elo_max = int(self.opp_elo_max.value()) if self.opp_elo_max else 0
        rows = self.controller.get_tree_game_children(
            pos_id,
            my_side_only=True,
            date_from=date_from,
            date_to=date_to,
            time_class=time_class,
            opp_elo_min=elo_min if elo_min > 0 else None,
            opp_elo_max=elo_max if elo_max > 0 else None,
        )
        if not rows:
            fallback = self.controller.get_tree_game_children(
                pos_id,
                my_side_only=False,
                date_from=date_from,
                date_to=date_to,
                time_class=time_class,
                opp_elo_min=elo_min if elo_min > 0 else None,
                opp_elo_max=elo_max if elo_max > 0 else None,
            )
            if fallback:
                self.status_label.setText(
                    "No my-side game moves here; showing all continuations."
                )
                rows = fallback
            else:
                self.status_label.setText("No game moves for current filters.")
        self.rows = rows
        self._populate_game_table(rows)

    def _current_pos_id(self) -> int | None:
        fen_norm = normalize_fen(self.board)
        return self.controller.get_position_id_by_fen(fen_norm)

    def _path_text(self) -> str:
        if not self.path_uci:
            return "(root)"
        temp = chess.Board()
        parts: list[str] = []
        for uci in self.path_uci:
            move = chess.Move.from_uci(uci)
            if move not in temp.legal_moves:
                break
            san = temp.san(move)
            if temp.turn == chess.WHITE:
                parts.append(f"{temp.fullmove_number}. {san}")
            else:
                parts.append(san)
            temp.push(move)
        return " ".join(parts) if parts else "(root)"

    def _display_move(self, row: dict) -> str:
        san = row.get("san_move")
        if san:
            return str(san)
        uci_move = row.get("uci_move")
        if not uci_move:
            return ""
        try:
            move = chess.Move.from_uci(str(uci_move))
        except ValueError:
            return str(uci_move)
        if move in self.board.legal_moves:
            return self.board.san(move)
        return str(uci_move)

    def _populate_repertoire_table(self, rows: list[dict]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self._display_move(row),
                str(int(row.get("weight") or 0)),
                "Yes" if int(row.get("is_priority_edge") or 0) > 0 else "",
                "Yes" if int(row.get("is_user_mainline") or 0) > 0 else "",
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col_index == 0:
                    item.setData(QtCore.Qt.UserRole, row)
                self.table.setItem(row_index, col_index, item)

    def _populate_game_table(self, rows: list[dict]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            games = int(row.get("games") or 0)
            wins = int(row.get("wins") or 0)
            draws = int(row.get("draws") or 0)
            losses = int(row.get("losses") or 0)
            avg_elo = row.get("avg_opp_elo")
            values = [
                self._display_move(row),
                str(games),
                f"{wins}/{draws}/{losses}",
                f"{float(row.get('score_pct') or 0.0):.1f}%",
                f"{float(avg_elo):.0f}" if avg_elo is not None else "",
            ]
            for col_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col_index == 0:
                    item.setData(QtCore.Qt.UserRole, row)
                self.table.setItem(row_index, col_index, item)
