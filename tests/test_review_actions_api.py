from __future__ import annotations

import asyncio
import sqlite3
import sys
import types
from pathlib import Path

python_multipart_module = types.ModuleType("python_multipart")
python_multipart_module.__version__ = "0.0.20"

multipart_module = types.ModuleType("multipart")
multipart_module.__version__ = "0.0.20"
multipart_submodule = types.ModuleType("multipart.multipart")


def _parse_options_header(value: str):
    return value, {}


multipart_submodule.parse_options_header = _parse_options_header
multipart_module.multipart = multipart_submodule
sys.modules.setdefault("python_multipart", python_multipart_module)
sys.modules.setdefault("multipart", multipart_module)
sys.modules.setdefault("multipart.multipart", multipart_submodule)

from backend import api_service
from storage import database


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO positions (id, fen_norm) VALUES (1, 'startpos')")
    conn.execute("INSERT INTO repertoire_lines (line_id, canonical_path_hash, side_to_play) VALUES ('line-1', 'hash-line-1', 'white')")
    conn.execute(
        """
        INSERT INTO trainer_line_state (line_id, side_to_play, priority_override)
        VALUES ('line-1', 'white', 0)
        """
    )
    conn.execute(
        """
        INSERT INTO review_propositions
        (id, proposition_type, proposition_key, status, evidence_count, threshold_count, pos_id, uci_move, line_id_hint, detail_json, created_at, updated_at)
        VALUES
        (101, 'MISSING_COVERAGE_BRANCH', 'p-101', 'PENDING', 7, 5, 1, 'e2e4', 'line-1', '{"evidence":["game-a"]}', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
        (102, 'MISSING_COVERAGE_BRANCH', 'p-102', 'PENDING', 9, 5, 1, 'd2d4', 'line-1', '{"evidence":["game-b"]}', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
        (103, 'MISSING_COVERAGE_BRANCH', 'p-103', 'PENDING', 8, 5, 1, 'c2c4', 'line-1', '{"evidence":["game-c"]}', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
        """
    )
    conn.commit()


def _configure_sqlite_backend(monkeypatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "review-actions.db"
    conn = database.ensure_db(str(db_path), reset_on_mismatch=True)
    _seed(conn)
    conn.close()

    class _Settings:
        data_backend = "sqlite"
        sqlite_path = str(db_path)

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    return db_path


def test_review_done_action_updates_status_and_queue(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_backend(monkeypatch, tmp_path)

    result = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=101, action="done"),
            _="dev-user",
        )
    )

    assert result.success is True
    assert result.proposition is not None
    assert result.proposition.status == "APPROVED"
    assert result.queue_change is not None
    assert result.queue_change.after is not None
    assert result.queue_change.after["queue_status"] == "QUEUED"

    queue = asyncio.run(api_service.list_review_branch_queue(_="dev-user"))
    assert len(queue) == 1
    assert queue[0].proposition_id == 101


def test_review_defer_action_removes_queue_and_disapproves(monkeypatch, tmp_path: Path) -> None:
    db_path = _configure_sqlite_backend(monkeypatch, tmp_path)

    # First queue the proposition.
    asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=102, action="done"),
            _="dev-user",
        )
    )

    result = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=102, action="defer"),
            _="dev-user",
        )
    )

    assert result.success is True
    assert result.proposition is not None
    assert result.proposition.status == "DISAPPROVED"
    assert result.queue_change is not None
    assert result.queue_change.after is None

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM branch_queue WHERE proposition_id = 102").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 0


def test_review_priority_action_sets_override_and_detail_endpoint(monkeypatch, tmp_path: Path) -> None:
    _configure_sqlite_backend(monkeypatch, tmp_path)

    result = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=103, action="priority"),
            _="dev-user",
        )
    )

    assert result.success is True
    assert result.priority_change is not None
    assert result.priority_change.before == 0
    assert result.priority_change.after == 1

    detail = asyncio.run(api_service.get_review_action(103, _="dev-user"))
    assert detail.id == 103
    assert detail.detail is not None
    assert "evidence" in detail.detail


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _Acquire(self._conn)


class _Request:
    def __init__(self, conn):
        self.app = types.SimpleNamespace(state=types.SimpleNamespace(db_pool=_Pool(conn)))


class _Tx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePgConn:
    def __init__(self):
        self.propositions = {
            201: {
                "id": 201,
                "proposition_type": "MISSING_COVERAGE_BRANCH",
                "proposition_key": "p-201",
                "status": "PENDING",
                "evidence_count": 7,
                "threshold_count": 5,
                "dismissed_count": None,
                "pos_id": 1,
                "uci_move": "e2e4",
                "line_id_hint": "line-1",
                "detail_json": '{"evidence":["game-a"]}',
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "decided_at": None,
            },
            202: {
                "id": 202,
                "proposition_type": "MISSING_COVERAGE_BRANCH",
                "proposition_key": "p-202",
                "status": "PENDING",
                "evidence_count": 9,
                "threshold_count": 5,
                "dismissed_count": None,
                "pos_id": 1,
                "uci_move": "d2d4",
                "line_id_hint": "line-1",
                "detail_json": '{"evidence":["game-b"]}',
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "decided_at": None,
            },
            203: {
                "id": 203,
                "proposition_type": "MISSING_COVERAGE_BRANCH",
                "proposition_key": "p-203",
                "status": "PENDING",
                "evidence_count": 8,
                "threshold_count": 5,
                "dismissed_count": None,
                "pos_id": 1,
                "uci_move": "c2c4",
                "line_id_hint": "line-1",
                "detail_json": '{"evidence":["game-c"]}',
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "decided_at": None,
            },
        }
        self.branch_queue = {}
        self.priority_override = {"line-1": 0}

    def transaction(self):
        return _Tx()

    async def fetch(self, query: str, *args):
        if "FROM review_propositions" in query and "ORDER BY evidence_count" in query:
            rows = [row for row in self.propositions.values() if row["proposition_type"] == "MISSING_COVERAGE_BRANCH"]
            if "status = 'PENDING'" in query:
                rows = [r for r in rows if r["status"] == "PENDING" and r["evidence_count"] > r["threshold_count"]]
            elif "status = 'APPROVED'" in query:
                rows = [r for r in rows if r["status"] == "APPROVED"]
            elif "status = 'DISAPPROVED'" in query:
                rows = [r for r in rows if r["status"] == "DISAPPROVED"]
            rows.sort(key=lambda r: (r["evidence_count"], r["updated_at"], r["id"]), reverse=True)
            return [
                {
                    "id": r["id"],
                    "proposition_type": r["proposition_type"],
                    "status": r["status"],
                    "evidence_count": r["evidence_count"],
                    "threshold_count": r["threshold_count"],
                    "pos_id": r["pos_id"],
                    "uci_move": r["uci_move"],
                    "line_id_hint": r["line_id_hint"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        if "FROM line_positions lp" in query and "WITH repertoire_rows" in query:
            return [
                {
                    "uci_move": "e2e4",
                    "san_move": "e4",
                    "next_pos_id": 2,
                    "weight": 3,
                    "is_priority_edge": 0,
                    "is_user_mainline": 1,
                    "self_count": 1,
                    "is_sideline_pending": 0,
                }
            ]
        if "FROM game_positions gp" in query and "COUNT(*)::int AS games" in query:
            return [
                {
                    "uci_move": "e2e4",
                    "san_move": "e4",
                    "next_pos_id": 2,
                    "games": 2,
                    "wins": 1,
                    "draws": 1,
                    "losses": 0,
                    "avg_opp_elo": 1800.0,
                }
            ]
        if "FROM branch_queue bq" in query and "ORDER BY bq.queued_at" in query:
            out = []
            for pid, q in self.branch_queue.items():
                rp = self.propositions[pid]
                out.append(
                    {
                        "proposition_id": pid,
                        "queue_status": q["queue_status"],
                        "queued_at": q["queued_at"],
                        "proposition_status": rp["status"],
                        "evidence_count": rp["evidence_count"],
                        "threshold_count": rp["threshold_count"],
                        "pos_id": rp["pos_id"],
                        "uci_move": rp["uci_move"],
                        "line_id_hint": rp["line_id_hint"],
                        "updated_at": rp["updated_at"],
                    }
                )
            out.sort(key=lambda r: (r["queued_at"] or "", r["proposition_id"]), reverse=True)
            return out
        return []

    async def fetchrow(self, query: str, *args):
        if "SELECT id, status, evidence_count, line_id_hint" in query:
            return self.propositions.get(int(args[0]))
        if "FROM review_propositions" in query and "detail_json" in query:
            return self.propositions.get(int(args[0]))
        if "FROM branch_queue bq" in query and "WHERE bq.proposition_id = $1" in query:
            pid = int(args[0])
            if pid not in self.branch_queue:
                return None
            rp = self.propositions[pid]
            q = self.branch_queue[pid]
            return {
                "proposition_id": pid,
                "queue_status": q["queue_status"],
                "queued_at": q["queued_at"],
                "proposition_status": rp["status"],
                "evidence_count": rp["evidence_count"],
                "threshold_count": rp["threshold_count"],
                "pos_id": rp["pos_id"],
                "uci_move": rp["uci_move"],
                "line_id_hint": rp["line_id_hint"],
                "updated_at": rp["updated_at"],
            }
        if "SELECT priority_override FROM trainer_line_state" in query:
            line_id = str(args[0])
            if line_id not in self.priority_override:
                return None
            return {"priority_override": self.priority_override[line_id]}
        return None

    async def execute(self, query: str, *args):
        if "UPDATE review_propositions" in query and "SET status = 'APPROVED'" in query:
            pid = int(args[0])
            prop = self.propositions.get(pid)
            if not prop:
                return "UPDATE 0"
            prop["status"] = "APPROVED"
            prop["decided_at"] = args[1]
            prop["updated_at"] = args[1]
            return "UPDATE 1"
        if "INSERT INTO branch_queue" in query:
            pid = int(args[0])
            self.branch_queue[pid] = {"queue_status": "QUEUED", "queued_at": args[1]}
            return "INSERT 1"
        if "SET status = 'DISAPPROVED'" in query:
            pid = int(args[0])
            prop = self.propositions[pid]
            prop["status"] = "DISAPPROVED"
            prop["dismissed_count"] = int(args[1])
            prop["decided_at"] = args[2]
            prop["updated_at"] = args[2]
            return "UPDATE 1"
        if "DELETE FROM branch_queue" in query:
            self.branch_queue.pop(int(args[0]), None)
            return "DELETE 1"
        if "SET priority_override = 1" in query:
            line_id = str(args[0])
            if line_id not in self.priority_override:
                return "UPDATE 0"
            self.priority_override[line_id] = 1
            return "UPDATE 1"
        if "UPDATE review_propositions" in query and "SET updated_at" in query:
            pid = int(args[0])
            self.propositions[pid]["updated_at"] = args[1]
            return "UPDATE 1"
        return "OK"


def test_review_actions_postgres_backend_paths(monkeypatch) -> None:
    class _Settings:
        data_backend = "postgres"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakePgConn()
    request = _Request(conn)

    listed = asyncio.run(api_service.list_review_actions(request=request, _="dev-user"))
    assert len(listed) == 3

    done = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=201, action="done"),
            request=request,
            _="dev-user",
        )
    )
    assert done.success is True
    assert done.proposition is not None
    assert done.proposition.status == "APPROVED"

    queue = asyncio.run(api_service.list_review_branch_queue(request=request, _="dev-user"))
    assert len(queue) == 1
    assert queue[0].proposition_id == 201

    deferred = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=202, action="defer"),
            request=request,
            _="dev-user",
        )
    )
    assert deferred.success is True
    assert deferred.proposition is not None
    assert deferred.proposition.status == "DISAPPROVED"

    prioritized = asyncio.run(
        api_service.execute_review_action(
            api_service.ReviewActionRequest(proposition_id=203, action="priority"),
            request=request,
            _="dev-user",
        )
    )
    assert prioritized.success is True
    assert prioritized.priority_change is not None
    assert prioritized.priority_change.before == 0
    assert prioritized.priority_change.after == 1

    detail = asyncio.run(api_service.get_review_action(203, request=request, _="dev-user"))
    assert detail.id == 203
    assert detail.detail is not None
    assert "evidence" in detail.detail


def test_tree_routes_use_postgres_backend_without_501(monkeypatch) -> None:
    class _Settings:
        data_backend = "postgres"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakePgConn()
    request = _Request(conn)

    browse = asyncio.run(api_service.get_lines_tree_browse(pos_id=1, request=request, _="dev-user"))
    assert browse.pos_id == 1
    assert len(browse.repertoire_children) == 1
    assert len(browse.game_children) == 1

    coverage = asyncio.run(api_service.get_lines_tree_coverage(pos_id=1, request=request, _="dev-user"))
    assert coverage.total_repertoire_moves == 1
    assert coverage.covered_by_games == 1

    metrics = asyncio.run(api_service.get_lines_tree_branch_metrics(pos_id=1, request=request, _="dev-user"))
    assert len(metrics.top_repertoire_branches) == 1
    assert len(metrics.top_game_branches) == 1
