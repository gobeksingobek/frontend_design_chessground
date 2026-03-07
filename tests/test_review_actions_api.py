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
