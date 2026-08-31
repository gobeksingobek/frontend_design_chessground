from __future__ import annotations

import io
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6 import QtWidgets

from app_config import AppConfig, ensure_config_values, read_config_file
from gui.main_window import MainWindow


class AppController:
    """Synchronous desktop facade over the backend HTTP API."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._analysis_lock = threading.Lock()
        self._analysis_running = False
        self._closing = False
        try:
            workspace = self._request("GET", "/settings/runtime")
            if isinstance(workspace, dict):
                self.config = config.with_workspace_settings(workspace)
        except Exception:
            # The first visible API operation will report the actionable connection error.
            pass

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        url = f"{self.config.backend_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Authorization": f"Bearer {self.config.api_token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                detail = json.loads(raw).get("detail", raw.decode("utf-8", errors="replace"))
            except Exception:
                detail = raw.decode("utf-8", errors="replace")
            raise RuntimeError(f"Backend request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot reach backend at {self.config.backend_url}: {exc.reason}") from exc
        return json.loads(raw) if raw else None

    def _upload(self, path: str, filename: str, payload: bytes) -> dict[str, Any]:
        boundary = f"----ChessGround{uuid.uuid4().hex}"
        body = io.BytesIO()
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
        body.write(b"Content-Type: application/octet-stream\r\n\r\n")
        body.write(payload)
        body.write(f"\r\n--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"{self.config.backend_url}{path}",
            data=body.getvalue(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_token}",
                "Idempotency-Key": f"desktop-upload-{uuid.uuid4()}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc

    def _archive_pgn_directory(self, directory: str) -> bytes | None:
        root = Path(directory)
        files = sorted({*root.rglob("*.pgn"), *root.rglob("*.PGN")}) if root.exists() else []
        if not files:
            return None
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in files:
                archive.write(source, source.relative_to(root).as_posix())
        return output.getvalue()

    def _wait_job(self, job_id: str, progress_cb=None) -> dict[str, Any]:
        while not self._closing:
            job = self._request("GET", f"/jobs/{job_id}")
            if progress_cb:
                progress_cb(dict(job.get("progress") or {}))
            if job["status"] == "completed":
                return job
            if job["status"] in {"failed", "cancelled"}:
                raise RuntimeError(job.get("error_detail") or f"Job {job['status']}")
            time.sleep(0.5)
        raise RuntimeError("Application is shutting down.")

    def _run_job(self, path: str, progress_cb=None) -> dict[str, Any]:
        with self._analysis_lock:
            if self._closing:
                raise RuntimeError("Application is shutting down.")
            if self._analysis_running:
                raise RuntimeError("Analysis is already running.")
            self._analysis_running = True
        try:
            accepted = self._request(
                "POST", path, {}, idempotency_key=f"desktop-{path.strip('/').replace('/', '-')}-{uuid.uuid4()}"
            )
            return self._wait_job(str(accepted["job_id"]), progress_cb)
        finally:
            with self._analysis_lock:
                self._analysis_running = False

    def _sync_local_sources(self, progress_cb=None) -> None:
        for directory, endpoint, label in (
            (self.config.repertoire_dir, "/repertoires/import", "repertoire"),
            (self.config.games_dir, "/games/import", "games"),
        ):
            archive = self._archive_pgn_directory(directory) if directory else None
            if archive is None:
                continue
            if progress_cb:
                progress_cb({"message": f"Uploading {label} PGNs", "done": 0, "total": 1})
            accepted = self._upload(endpoint, f"desktop-{label}.zip", archive)
            self._wait_job(str(accepted["job_id"]), progress_cb)

    def is_analysis_running(self) -> bool:
        with self._analysis_lock:
            return self._analysis_running

    def run_analysis(self, reset_db: bool = False, progress_cb=None) -> None:
        self._sync_local_sources(progress_cb)
        self._run_job("/analysis/run/full" if reset_db else "/analysis/run/incremental", progress_cb)

    def run_engine_analysis_only(self, progress_cb=None) -> None:
        self._run_job("/analysis/run/engine-only", progress_cb)

    def run_line_matching_reanalysis(self, progress_cb=None) -> None:
        self._run_job("/analysis/run/line-matching", progress_cb)

    def run_game_details_reanalysis(self, progress_cb=None) -> None:
        self._run_job("/analysis/run/game-details", progress_cb)

    def run_smoke_test(self, progress_cb=None) -> dict[str, Any]:
        return self._run_job("/analysis/run/smoke-test", progress_cb)

    def get_path_summary(self) -> str:
        return (
            f"Backend: {self.config.backend_url}\n"
            f"Repertoire upload directory: {self.config.repertoire_dir or 'Not configured'}\n"
            f"Game upload directory: {self.config.games_dir or 'Not configured'}\n"
            f"Pieces: {self.config.piece_dir}"
        )

    def get_overview_summary(self) -> str:
        row = self._request("GET", "/overview/summary")
        return (
            f"Lines: {row['lines']} | Manual priority: {row['manual_priority']} | "
            f"Auto-priority: {row['auto_priority']} | Games: {row['games']} | "
            f"Matched: {row['matched']} | Fully compliant: {row['fully_compliant']}"
        )

    def get_game_overview(self) -> list[dict[str, Any]]:
        return self._request("GET", "/games?limit=200")

    get_game_summaries = get_game_overview
    get_games_list = get_game_overview

    def _game_detail(self, game_id: int) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/games/{game_id}")
        except RuntimeError as exc:
            if "404" in str(exc):
                return None
            raise

    def get_game_header(self, game_id: int) -> dict[str, Any] | None:
        detail = self._game_detail(game_id)
        return detail.get("header") if detail else None

    def get_game_moves(self, game_id: int) -> list[dict[str, Any]]:
        detail = self._game_detail(game_id)
        return list(detail.get("moves") or []) if detail else []

    def get_line_moves(self, line_id: str, max_ply: int | None = None) -> list[dict[str, Any]]:
        query = "" if max_ply is None else f"?max_ply={int(max_ply)}"
        return self._request("GET", f"/lines/{urllib.parse.quote(line_id, safe='')}/moves{query}")

    def get_line_edge(self, line_id: str, ply: int) -> dict[str, Any] | None:
        return next((row for row in self.get_line_moves(line_id, ply) if int(row.get("ply") or 0) == ply), None)

    def get_position_id_by_fen(self, fen_norm: str) -> int | None:
        row = self._request("GET", f"/positions/by-fen/lookup?fen={urllib.parse.quote(fen_norm)}")
        return int(row["pos_id"]) if row else None

    def _tree(self, pos_id: int, my_side_only: bool) -> dict[str, Any]:
        return self._request("GET", f"/lines/tree/browse?pos_id={pos_id}&my_side_only={str(my_side_only).lower()}")

    def get_tree_repertoire_children(self, pos_id: int, my_side_only: bool = True) -> list[dict[str, Any]]:
        return list(self._tree(pos_id, my_side_only).get("repertoire_children") or [])

    def get_tree_game_children(self, pos_id: int, *, my_side_only: bool = True, **_filters) -> list[dict[str, Any]]:
        return list(self._tree(pos_id, my_side_only).get("game_children") or [])

    def get_tree_position_games(self, pos_id: int, uci_move: str, limit: int = 20) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"uci_move": uci_move, "limit": int(limit)})
        return self._request("GET", f"/positions/{int(pos_id)}/games?{query}")

    def set_user_mainline(self, pos_id: int, uci_move: str, next_pos_id: int) -> None:
        self._request("POST", f"/positions/{pos_id}/mainline", {"uci_move": uci_move, "next_pos_id": next_pos_id})

    def reanalyze_game(self, game_id: int) -> None:
        self._run_job(f"/games/{int(game_id)}/reanalyze")

    def compute_deviation_rep_cpl(self, game_id: int, ply: int) -> dict[str, Any]:
        try:
            self.reanalyze_game(game_id)
            move = next((row for row in self.get_game_moves(game_id) if int(row.get("ply") or 0) == ply), None)
            return {"success": True, "rep_cpl": move.get("rep_cpl") if move else None, "message": "Server reanalysis completed."}
        except Exception as exc:
            return {"success": False, "rep_cpl": None, "message": str(exc)}

    def get_line_stats(self) -> list[dict[str, Any]]:
        return self._request("GET", "/lines/stats")

    def get_month_stats(self) -> list[dict[str, Any]]:
        return self._request("GET", "/statistics/months")

    def get_rating_band_stats(self, band_size: int) -> list[dict[str, Any]]:
        return list(self._request("GET", f"/rating-bands/stats?band_size={band_size}").get("buckets") or [])

    def get_time_pattern_summary(self) -> dict[str, int]:
        return self._request("GET", "/time-patterns/summary")

    def get_review_items(self) -> list[dict[str, Any]]:
        return self._request("GET", "/review/items")

    def get_review_propositions(self, status_filter: str = "pending") -> list[dict[str, Any]]:
        return self._request("GET", f"/review/actions?status={urllib.parse.quote(status_filter)}")

    def get_review_proposition_detail(self, proposition_id: int) -> dict[str, Any] | None:
        return self._request("GET", f"/review/actions/{proposition_id}")

    def _review_action(self, proposition_id: int, action: str) -> tuple[bool, str]:
        try:
            result = self._request("POST", "/review/actions", {"proposition_id": proposition_id, "action": action})
            return bool(result.get("success")), str(result.get("message") or "")
        except RuntimeError as exc:
            return False, str(exc)

    def approve_review_proposition(self, proposition_id: int) -> tuple[bool, str]:
        return self._review_action(proposition_id, "done")

    def disapprove_review_proposition(self, proposition_id: int) -> tuple[bool, str]:
        return self._review_action(proposition_id, "defer")

    def request_sideline_for_game_deviation(self, game_id: int) -> tuple[bool, str, dict[str, Any] | None]:
        detail = self._game_detail(game_id)
        if not detail:
            return False, "Game not found.", None
        header = detail.get("header") or {}
        deviation_ply = header.get("deviation_ply_you") or header.get("deviation_ply_opp")
        if deviation_ply is None:
            return False, "This game has no recorded repertoire deviation.", None
        move = next(
            (row for row in detail.get("moves") or [] if int(row.get("ply") or 0) == int(deviation_ply)),
            None,
        )
        if not move or not move.get("fen") or not move.get("uci_move"):
            return False, "The deviation does not have enough persisted move data for analysis.", None
        try:
            item = self._request(
                "POST",
                "/sidelines",
                {
                    "game_id": str(game_id),
                    "move_ply": int(deviation_ply),
                    "fen": str(move["fen"]),
                    "branch_moves": [str(move["uci_move"])],
                },
                idempotency_key=f"desktop-sideline-{game_id}-{deviation_ply}-{move['uci_move']}",
            )
            item = {**item, "request_count": 1, "queue_key": item.get("id")}
            return True, "Server sideline analysis queued.", item
        except RuntimeError as exc:
            return False, str(exc), None

    def get_insights(self) -> list[dict[str, Any]]:
        return self._request("GET", "/insights")

    def ensure_trainer_sync(self) -> None:
        if self.config.repertoire_dir:
            archive = self._archive_pgn_directory(self.config.repertoire_dir)
            if archive:
                accepted = self._upload("/repertoires/import", "desktop-repertoire.zip", archive)
                self._wait_job(str(accepted["job_id"]))

    def _trainer_queue(self, mode: str) -> list[dict[str, Any]]:
        return list(self._request("GET", f"/trainer/queue?mode={urllib.parse.quote(mode)}").get("items") or [])

    def get_trainer_line(self, line_id: str) -> dict[str, Any] | None:
        row = next((item for item in self._trainer_queue("review") + self._trainer_queue("learn") if item.get("line_id") == line_id), None)
        if row:
            row = {**row, "moves": self.get_line_moves(line_id)}
        return row

    def select_next_trainer_line(self, mode: str) -> str | None:
        rows = self._trainer_queue(mode)
        if not rows:
            return None
        rows.sort(key=lambda row: (-int(row.get("auto_priority_score") or 0), int(row.get("correct_streak") or 0)))
        tied = [row for row in rows if (row.get("auto_priority_score"), row.get("correct_streak")) == (rows[0].get("auto_priority_score"), rows[0].get("correct_streak"))]
        return str(random.choice(tied)["line_id"])

    def update_trainer_state(self, line_id: str, learned: int | None = None, needs_review: int | None = None, correct_streak: int | None = None, times_correct_delta: int = 0, times_incorrect_delta: int = 0) -> None:
        correct = times_incorrect_delta == 0 and (times_correct_delta > 0 or needs_review == 0)
        self._request("POST", "/trainer/outcomes", {"line_id": line_id, "is_correct": correct, "mode": "learn" if learned else "review"})

    def toggle_trainer_priority(self, line_id: str) -> int:
        row = self.get_trainer_line(line_id) or {}
        value = -1 if int(row.get("priority_override") or 0) == 1 else 1
        self.set_trainer_priority_override(line_id, value)
        return value

    def set_trainer_priority_override(self, line_id: str, value: int) -> None:
        self._request("POST", "/trainer/priority-override", {"line_id": line_id, "value": value})

    def discard_trainer_line(self, line_id: str, discard_path: Path) -> tuple[bool, str]:
        try:
            self._request("DELETE", f"/trainer/lines/{urllib.parse.quote(line_id, safe='')}")
            return True, "Line removed from the workspace repertoire."
        except RuntimeError as exc:
            return False, str(exc)

    def fetch_games(self, variants: list[str]) -> dict[str, Any]:
        try:
            if variants:
                self._request("PUT", "/settings/runtime", {"variants": variants})
            job = self._run_job("/analysis/run/fetch-games")
            result = job.get("result") or {}
            return {"success": True, "message": "Fetch completed.", "total_new_games": int(result.get("games_inserted") or 0), "total_seen_games": int(result.get("games_parsed") or 0), "had_source_errors": False}
        except Exception as exc:
            return {"success": False, "message": str(exc), "total_new_games": 0, "total_seen_games": 0, "had_source_errors": True}

    def apply_config(self, config: AppConfig) -> None:
        if self._closing:
            raise RuntimeError("Application is shutting down.")
        self.config = config
        workspace = self._request(
            "PUT",
            "/settings/runtime",
            {
                "rating_band_size": int(config.rating_band_size),
                "variants": list(config.fetch_variants or []),
            },
        )
        if isinstance(workspace, dict):
            self.config = config.with_workspace_settings(workspace)

    def close(self) -> None:
        self._closing = True


def main() -> int:
    settings_path = BASE_DIR / "config" / "settings.ini"
    config = ensure_config_values(read_config_file(settings_path), BASE_DIR)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    controller = AppController(config)
    window = MainWindow(controller, settings_path)
    app.aboutToQuit.connect(window.on_app_about_to_quit)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
