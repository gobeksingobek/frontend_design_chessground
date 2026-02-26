from __future__ import annotations

import sys
import random
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6 import QtWidgets

from analysis import statistics
from analysis import pipeline as analysis_pipeline
from analysis import game_fetcher
from analysis import smoke_test as smoke_test_module
from app_config import ensure_config_values, read_config_file
from gui.main_window import MainWindow
from storage import database, queries

ALLOWED_FETCH_VARIANTS = {"blitz", "rapid", "daily"}


def run_startup_randomizer() -> tuple[bool, str]:
    repo_root = BASE_DIR.parent
    script_path = repo_root / "pgn_randomizer.py"
    if not script_path.exists():
        return False, f"Startup randomizer not found: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return False, f"Failed to run startup randomizer: {exc}"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else "Randomizer finished."
    if result.returncode != 0:
        detail = stderr or summary or "Unknown error"
        return False, (
            f"Startup randomizer failed (exit {result.returncode}). {detail}"
        )
    return True, summary


class AppController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.conn = database.ensure_db(config.database_path, reset_on_mismatch=True)
        self._analysis_lock = threading.Lock()
        self._analysis_running = False
        self._closing = False

    def _set_analysis_running(self, running: bool) -> None:
        with self._analysis_lock:
            self._analysis_running = running

    def is_analysis_running(self) -> bool:
        with self._analysis_lock:
            return self._analysis_running

    def _run_with_analysis_conn(self, action) -> None:
        with self._analysis_lock:
            if self._closing:
                raise RuntimeError("Application is shutting down.")
            if self._analysis_running:
                raise RuntimeError("Analysis is already running.")
            self._analysis_running = True
        conn = None
        last_sql: dict[str, str] = {"value": ""}
        try:
            conn = database.ensure_db(self.config.database_path, reset_on_mismatch=True)
            conn.set_trace_callback(lambda sql: last_sql.__setitem__("value", sql))
            action(conn)
        except sqlite3.IntegrityError as exc:
            msg = str(exc)
            if "FOREIGN KEY constraint failed" in msg:
                # Snapshot the failing statement before running diagnostics.
                last_stmt = (last_sql.get("value") or "").strip().replace("\n", " ")
                fk_rows = []
                try:
                    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchmany(5)
                except sqlite3.Error:
                    fk_rows = []
                sql_preview = last_stmt
                if len(sql_preview) > 240:
                    sql_preview = sql_preview[:240] + "..."
                detail = (
                    "Foreign key constraint failed during analysis. "
                    f"Last SQL: {sql_preview or '<none>'}. "
                    f"foreign_key_check (first rows): {fk_rows}"
                )
                raise RuntimeError(detail) from exc
            raise
        except sqlite3.OperationalError as exc:
            msg = str(exc)
            if "readonly" in msg.lower() or "disk i/o" in msg.lower():
                raise RuntimeError(
                    "Database path is not writable for SQLite journaling: "
                    f"{self.config.database_path}. "
                    "Choose a user-writable path (for example "
                    "C:\\Users\\<you>\\AppData\\Local\\Temp\\repertoire_analysis.db)."
                ) from exc
            raise
        finally:
            if conn is not None:
                conn.set_trace_callback(None)
                conn.close()
            self._set_analysis_running(False)

    def _run_with_analysis_lock(self, action):
        with self._analysis_lock:
            if self._closing:
                raise RuntimeError("Application is shutting down.")
            if self._analysis_running:
                raise RuntimeError("Analysis is already running.")
            self._analysis_running = True
        try:
            return action()
        finally:
            self._set_analysis_running(False)

    def run_analysis(
        self,
        reset_db: bool = False,
        progress_cb=None,
    ) -> None:
        self._run_with_analysis_conn(
            lambda conn: analysis_pipeline.run_analysis(
                conn, self.config, reset_db=reset_db, progress_cb=progress_cb
            )
        )

    def run_engine_analysis_only(self, progress_cb=None) -> None:
        self._run_with_analysis_conn(
            lambda conn: analysis_pipeline.run_engine_analysis_only(
                conn, self.config, progress_cb=progress_cb
            )
        )

    def run_line_matching_reanalysis(self, progress_cb=None) -> None:
        self._run_with_analysis_conn(
            lambda conn: analysis_pipeline.run_line_matching_reanalysis(
                conn, self.config, progress_cb=progress_cb
            )
        )

    def run_game_details_reanalysis(self, progress_cb=None) -> None:
        self._run_with_analysis_conn(
            lambda conn: analysis_pipeline.run_game_details_reanalysis(
                conn, self.config, progress_cb=progress_cb
            )
        )

    def run_smoke_test(self, progress_cb=None) -> dict:
        return self._run_with_analysis_lock(
            lambda: smoke_test_module.run_smoke_test(
                self.config,
                BASE_DIR.parent,
                progress_cb=progress_cb,
            )
        )

    def get_path_summary(self) -> str:
        player_names = ", ".join(self.config.player_names) or self.config.player_name
        chesscom_users = ", ".join(self.config.chesscom_usernames)
        lichess_users = ", ".join(self.config.lichess_usernames)
        return (
            f"Repertoire dir: {self.config.repertoire_dir}\n"
            f"Games dir: {self.config.games_dir}\n"
            f"Database: {self.config.database_path}\n"
            f"Stockfish: {self.config.stockfish_path}\n"
            f"Pieces: {self.config.piece_dir}\n"
            f"Player(s): {player_names}\n"
            f"Chess.com fetch: {chesscom_users or 'N/A'}\n"
            f"Lichess fetch: {lichess_users or 'N/A'}"
        )

    def get_overview_summary(self) -> str:
        lines = self.conn.execute("SELECT COUNT(*) AS count FROM repertoire_lines").fetchone()[0]
        games = self.conn.execute("SELECT COUNT(*) AS count FROM games").fetchone()[0]
        matches = self.conn.execute("SELECT COUNT(*) AS count FROM matches").fetchone()[0]
        compliant = self.conn.execute(
            "SELECT COUNT(*) AS count FROM matches WHERE compliance = 'FULLY_COMPLIANT'"
        ).fetchone()[0]
        manual_priority = self.conn.execute(
            "SELECT COUNT(*) AS count FROM repertoire_lines WHERE is_priority = 1"
        ).fetchone()[0]
        auto_priority = self.conn.execute(
            "SELECT COUNT(*) AS count FROM trainer_line_state WHERE auto_priority_score > 0"
        ).fetchone()[0]
        return (
            f"Lines: {lines} | Manual priority: {manual_priority} | "
            f"Auto-priority: {auto_priority} | Games: {games} | "
            f"Matched: {matches} | Fully compliant: {compliant}"
        )

    def get_game_overview(self) -> list[dict]:
        return queries.fetch_game_overview(self.conn)

    def get_game_summaries(self) -> list[dict]:
        return queries.fetch_game_summaries(self.conn)

    def get_games_list(self) -> list[dict]:
        return queries.fetch_games_list(self.conn)

    def get_game_header(self, game_id: int) -> dict | None:
        return queries.fetch_game_header(self.conn, game_id)

    def get_game_moves(self, game_id: int) -> list[dict]:
        return queries.fetch_game_moves(self.conn, game_id)

    def get_line_moves(self, line_id: str, max_ply: int | None = None) -> list[dict]:
        return queries.fetch_line_moves(self.conn, line_id, max_ply)

    def get_line_edge(self, line_id: str, ply: int) -> dict | None:
        return queries.fetch_line_edge(self.conn, line_id, ply)

    def get_position_id_by_fen(self, fen_norm: str) -> int | None:
        return queries.fetch_position_id_by_fen(self.conn, fen_norm)

    def get_tree_repertoire_children(
        self,
        pos_id: int,
        my_side_only: bool = True,
    ) -> list[dict]:
        return queries.fetch_tree_repertoire_children(
            self.conn,
            pos_id,
            my_side_only=my_side_only,
        )

    def get_tree_game_children(
        self,
        pos_id: int,
        *,
        my_side_only: bool = True,
        date_from: str | None = None,
        date_to: str | None = None,
        time_class: str = "all",
        opp_elo_min: int | None = None,
        opp_elo_max: int | None = None,
    ) -> list[dict]:
        return queries.fetch_tree_game_children(
            self.conn,
            pos_id,
            my_side_only=my_side_only,
            date_from=date_from,
            date_to=date_to,
            time_class=time_class,
            opp_elo_min=opp_elo_min,
            opp_elo_max=opp_elo_max,
        )

    def get_tree_position_games(
        self,
        pos_id: int,
        uci_move: str,
        limit: int = 20,
    ) -> list[dict]:
        return queries.fetch_tree_position_games(
            self.conn,
            pos_id,
            uci_move,
            limit=limit,
        )

    def set_user_mainline(self, pos_id: int, uci_move: str, next_pos_id: int) -> None:
        queries.set_user_mainline(self.conn, pos_id, uci_move, next_pos_id)

    def reanalyze_game(self, game_id: int) -> None:
        with self._analysis_lock:
            if self._closing:
                raise RuntimeError("Application is shutting down.")
        if self.is_analysis_running():
            raise RuntimeError(
                "Cannot reanalyze a single game while analysis is running."
            )
        conn = database.ensure_db(self.config.database_path, reset_on_mismatch=True)
        try:
            analysis_pipeline.reanalyze_game(conn, self.config, game_id)
        finally:
            conn.close()

    def compute_deviation_rep_cpl(self, game_id: int, ply: int) -> dict[str, object]:
        with self._analysis_lock:
            if self._closing:
                return {
                    "success": False,
                    "rep_cpl": None,
                    "message": "Application is shutting down.",
                }
        if self.is_analysis_running():
            return {
                "success": False,
                "rep_cpl": None,
                "message": "Cannot compute Rep CPL while analysis is running.",
            }
        conn = database.ensure_db(self.config.database_path, reset_on_mismatch=True)
        try:
            rep_cpl, error = analysis_pipeline.compute_deviation_rep_cpl(
                conn,
                self.config,
                int(game_id),
                int(ply),
            )
            if error:
                return {
                    "success": False,
                    "rep_cpl": None,
                    "message": error,
                }
            return {
                "success": True,
                "rep_cpl": rep_cpl,
                "message": "Rep CPL updated." if rep_cpl is not None else "Rep CPL unavailable.",
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "success": False,
                "rep_cpl": None,
                "message": str(exc),
            }
        finally:
            conn.close()

    def get_line_stats(self) -> list[dict]:
        return statistics.aggregate_by_line(self.conn)

    def get_month_stats(self) -> list[dict]:
        return statistics.aggregate_by_month(self.conn)

    def get_rating_band_stats(self, band_size: int) -> list[dict]:
        return statistics.aggregate_by_rating_band(self.conn, band_size)

    def get_time_pattern_summary(self) -> dict:
        row = self.conn.execute(
            """
            SELECT SUM(slow_in_book) AS slow_in_book,
                   SUM(instant_out_of_book) AS instant_out_of_book,
                   SUM(blunder_cluster) AS blunder_cluster
            FROM time_patterns
            """
        ).fetchone()
        if not row:
            return {}
        return {
            "slow_in_book": row["slow_in_book"] or 0,
            "instant_out_of_book": row["instant_out_of_book"] or 0,
            "blunder_cluster": row["blunder_cluster"] or 0,
        }

    def get_review_items(self) -> list[dict]:
        return queries.fetch_review_items(self.conn)

    def get_review_propositions(self, status_filter: str = "pending") -> list[dict]:
        return queries.fetch_review_propositions(self.conn, status_filter=status_filter)

    def get_review_proposition_detail(self, proposition_id: int) -> dict | None:
        return queries.fetch_review_proposition_detail(self.conn, proposition_id)

    def approve_review_proposition(self, proposition_id: int) -> tuple[bool, str]:
        with self._analysis_lock:
            if self._closing:
                return False, "Application is shutting down."
            if self._analysis_running:
                return False, "Analysis is running. Try again after completion."
        return queries.approve_review_proposition(self.conn, proposition_id)

    def disapprove_review_proposition(self, proposition_id: int) -> tuple[bool, str]:
        with self._analysis_lock:
            if self._closing:
                return False, "Application is shutting down."
            if self._analysis_running:
                return False, "Analysis is running. Try again after completion."
        return queries.disapprove_review_proposition(self.conn, proposition_id)

    def get_insights(self) -> list[dict]:
        return queries.fetch_insights(self.conn)

    def ensure_trainer_sync(self) -> None:
        conn = database.ensure_db(self.config.database_path, reset_on_mismatch=True)
        try:
            analysis_pipeline.sync_repertoire_only(conn, self.config)
        finally:
            conn.close()

    def get_trainer_line(self, line_id: str) -> dict | None:
        info = queries.fetch_trainer_line_info(self.conn, line_id)
        if not info:
            return None
        moves = queries.fetch_line_moves(self.conn, line_id)
        info["moves"] = moves
        return info

    def select_next_trainer_line(self, mode: str) -> str | None:
        learned_only = mode == "review"
        candidates = queries.fetch_trainer_candidates(self.conn, learned_only)
        if not candidates:
            return None

        def tier(entry: dict) -> int:
            override = entry.get("priority_override")
            auto_score = int(entry.get("auto_priority_score") or 0)
            needs_review = bool(entry.get("needs_review"))
            adaptive_focus = entry.get("focus_max_ply") is not None

            if override == -1:
                manual_priority_effective = False
                auto_marked_effective = False
                adaptive_effective = False
            elif override == 1:
                manual_priority_effective = True
                auto_marked_effective = auto_score > 0
                adaptive_effective = adaptive_focus
            else:
                manual_priority_effective = bool(entry.get("is_priority"))
                auto_marked_effective = auto_score > 0
                adaptive_effective = adaptive_focus

            # Learn mode prioritizes adaptive-focus lines first.
            if not learned_only:
                # Learn ignores needs_review and selects by:
                # 1) adaptive focus
                # 2) auto-marked
                # 3) manual priority
                # 4) normal
                if adaptive_effective:
                    return 0
                if auto_marked_effective:
                    return 1
                if manual_priority_effective:
                    return 2
                return 3

            # Review mode order remains unchanged.
            # 1) auto + needs_review
            # 2) manual + needs_review
            # 3) auto
            # 4) manual
            # 5) needs_review
            # 6) normal
            if auto_marked_effective and needs_review:
                return 0
            if manual_priority_effective and needs_review:
                return 1
            if auto_marked_effective:
                return 2
            if manual_priority_effective:
                return 3
            if needs_review:
                return 4
            return 5

        best_tier = min(tier(entry) for entry in candidates)
        pool = [entry for entry in candidates if tier(entry) == best_tier]

        # Deterministic precedence inside tier:
        # 1) highest auto score first
        # 2) lower streak first
        # 3) random among exact ties
        def sort_key(entry: dict) -> tuple[int, int]:
            auto_score = int(entry.get("auto_priority_score") or 0)
            streak = int(entry.get("correct_streak") or 0)
            return (-auto_score, streak)

        pool.sort(key=sort_key)
        best_key = sort_key(pool[0])
        tied = [entry for entry in pool if sort_key(entry) == best_key]
        chosen = random.choice(tied)
        return chosen.get("line_id")

    def update_trainer_state(
        self,
        line_id: str,
        learned: int | None = None,
        needs_review: int | None = None,
        correct_streak: int | None = None,
        times_correct_delta: int = 0,
        times_incorrect_delta: int = 0,
    ) -> None:
        queries.update_trainer_state(
            self.conn,
            line_id,
            learned=learned,
            needs_review=needs_review,
            correct_streak=correct_streak,
            times_correct_delta=times_correct_delta,
            times_incorrect_delta=times_incorrect_delta,
            last_seen=datetime.now(timezone.utc).isoformat(),
        )

    def toggle_trainer_priority(self, line_id: str) -> int:
        return queries.toggle_trainer_priority(self.conn, line_id)

    def set_trainer_priority_override(self, line_id: str, value: int) -> None:
        queries.set_trainer_priority_override(self.conn, line_id, value)

    def discard_trainer_line(self, line_id: str, discard_path: Path) -> tuple[bool, str]:
        return analysis_pipeline.discard_repertoire_line(
            self.conn, line_id, discard_path
        )

    def fetch_games(self, variants: list[str]) -> dict[str, object]:
        with self._analysis_lock:
            if self._closing:
                return {
                    "success": False,
                    "message": "Application is shutting down.",
                    "total_new_games": 0,
                    "total_seen_games": 0,
                    "had_source_errors": True,
                }
        input_variants = [str(v).strip().lower() for v in (variants or []) if str(v).strip()]
        variants = []
        seen = set()
        for variant in input_variants:
            if variant not in ALLOWED_FETCH_VARIANTS:
                continue
            if variant in seen:
                continue
            seen.add(variant)
            variants.append(variant)
        bullet_ignored = "bullet" in input_variants
        if not variants:
            message = "No supported variants selected (supported: blitz, rapid, daily)."
            if bullet_ignored:
                message = f"{message} Bullet is disabled and was ignored."
            return {
                "success": False,
                "message": message,
                "total_new_games": 0,
                "total_seen_games": 0,
                "had_source_errors": False,
            }

        games_root = Path(self.config.games_dir)
        state_path = Path(self.config.database_path).parent / "fetch_state.json"
        fetch_conn = database.ensure_db(
            self.config.database_path, reset_on_mismatch=True
        )
        try:
            existing_rows = fetch_conn.execute("SELECT pgn_hash FROM games").fetchall()
            existing_hashes = {
                (row["pgn_hash"] if isinstance(row, sqlite3.Row) else row[0])
                for row in existing_rows
                if (row["pgn_hash"] if isinstance(row, sqlite3.Row) else row[0])
            }
        finally:
            fetch_conn.close()
        summaries = game_fetcher.fetch_games(
            games_dir=games_root,
            chesscom_usernames=self.config.chesscom_usernames,
            lichess_usernames=self.config.lichess_usernames,
            variants=variants,
            days_back=self.config.fetch_days_back,
            state_path=state_path,
            existing_pgn_hashes=existing_hashes,
        )
        if not summaries:
            return {
                "success": False,
                "message": "No fetch configured.",
                "total_new_games": 0,
                "total_seen_games": 0,
                "had_source_errors": False,
            }
        lines = []
        total_new_games = 0
        total_seen_games = 0
        had_source_errors = False
        for summary in summaries:
            if summary.source == "all":
                lines.append(summary.message)
                continue
            total_new_games += int(summary.games_written or 0)
            total_seen_games += int(summary.games_seen or 0)
            lines.append(
                f"{summary.source}:{summary.username} "
                f"files {summary.fetched_files} "
                f"skipped {summary.skipped_files} "
                f"seen {summary.games_seen} "
                f"new {summary.games_written} "
                f"db-skipped {summary.games_skipped_in_db}"
            )
            if summary.message:
                lines.append(f"{summary.source}:{summary.username} {summary.message}")
                msg = summary.message.lower()
                if (
                    "fetch failed" in msg
                    or "username not found" in msg
                    or "rate limited" in msg
                ):
                    had_source_errors = True
        message_text = " | ".join(lines)
        if bullet_ignored:
            message_text = f"{message_text} | Bullet is disabled and was ignored."
        return {
            "success": True,
            "message": message_text,
            "total_new_games": total_new_games,
            "total_seen_games": total_seen_games,
            "had_source_errors": had_source_errors,
        }

    def apply_config(self, config: AppConfig) -> None:
        with self._analysis_lock:
            if self._closing:
                raise RuntimeError("Application is shutting down.")
        if config.database_path != self.config.database_path:
            db_parent = Path(config.database_path).parent
            db_parent.mkdir(parents=True, exist_ok=True)
            self.conn.close()
            self.conn = database.ensure_db(config.database_path, reset_on_mismatch=True)
        self.config = config

    def close(self) -> None:
        with self._analysis_lock:
            if self._closing and self.conn is None:
                return
            self._closing = True
            conn = self.conn
            self.conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def main() -> int:
    base_dir = BASE_DIR
    settings_path = base_dir / "config" / "settings.ini"

    config = read_config_file(settings_path)

    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(
        """
        QMainWindow { background: #1c1f24; color: #e6e6e6; }
        QLabel { color: #e6e6e6; }
        QTabWidget::pane { border: 1px solid #2b2f36; background: #22262d; }
        QTabBar::tab { padding: 6px 12px; margin: 2px; background: #2a2f37; color: #e6e6e6; border-radius: 4px; }
        QTabBar::tab:selected { background: #2f3540; border: 1px solid #3a404b; }
        QPushButton { background: #2f6f6f; color: #f0f4f4; border-radius: 4px; padding: 4px 10px; }
        QPushButton:disabled { background: #465c5c; color: #c7c7c7; }
        QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #1f232a; color: #e6e6e6; border: 1px solid #3a404b; }
        QTableWidget { background: #1f232a; color: #e6e6e6; gridline-color: #343a45; }
        QHeaderView::section { background: #2a2f37; color: #e6e6e6; padding: 4px; border: 1px solid #343a45; }
        QGroupBox { border: 1px solid #343a45; border-radius: 4px; margin-top: 6px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; color: #e6e6e6; }
        """
    )
    app_config = ensure_config_values(config, base_dir)

    randomizer_ok, randomizer_msg = run_startup_randomizer()
    if randomizer_ok:
        print(f"[startup randomizer] {randomizer_msg}")
    else:
        print(f"[startup randomizer] {randomizer_msg}")
        QtWidgets.QMessageBox.warning(
            None,
            "Startup Randomizer Warning",
            randomizer_msg,
        )

    controller = AppController(app_config)
    window = MainWindow(controller, settings_path)
    app.aboutToQuit.connect(window.on_app_about_to_quit)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
