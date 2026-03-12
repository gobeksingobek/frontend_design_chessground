from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass, field

from fastapi import HTTPException

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

from pydantic import ValidationError

from backend import api_service


@dataclass
class _State:
    side_to_play: str = "white"
    learned: int = 0
    needs_review: int = 0
    correct_streak: int = 0
    times_correct: int = 0
    times_incorrect: int = 0


@dataclass
class _FakeConn:
    state: _State = field(default_factory=_State)
    sessions: dict[str, dict] = field(default_factory=dict)

    async def execute(self, query: str, *args):
        if "UPDATE trainer_sessions" in query:
            sid = args[0]
            self.sessions[sid]["player_move_index"] = int(args[1])
            self.sessions[sid]["had_incorrect"] = int(args[2])
            self.sessions[sid]["completed"] = int(args[3])
            return "UPDATE 1"
        if "SET learned = 1" in query and "times_correct" in query:
            completed = bool(args[1])
            self.state.learned = 1
            self.state.needs_review = 0
            if completed:
                self.state.correct_streak += 1
                self.state.times_correct += 1
            return "UPDATE 1"
        if "SET needs_review = 1" in query:
            self.state.needs_review = 1
            self.state.correct_streak = 0
            self.state.times_incorrect += 1
            return "UPDATE 1"
        return "OK"

    async def fetch(self, query: str, *args):
        if "FROM line_positions lp" in query:
            return [
                {"ply": 1, "san_move": "e4", "uci_move": "e2e4", "pos_id": 1, "next_pos_id": 2, "fen": "fen-1"},
                {"ply": 2, "san_move": "e5", "uci_move": "e7e5", "pos_id": 2, "next_pos_id": 3, "fen": "fen-2"},
                {"ply": 3, "san_move": "Nf3", "uci_move": "g1f3", "pos_id": 3, "next_pos_id": 4, "fen": "fen-3"},
            ]
        return []

    async def fetchrow(self, query: str, *args):
        if "SELECT rl.line_id" in query and "WHERE tls.learned = $1" in query:
            return {"line_id": "line-1"}
        if "FROM repertoire_lines rl" in query and "JOIN trainer_line_state" in query:
            line_id = args[0]
            if line_id != "line-1":
                return None
            return {
                "line_id": "line-1",
                "side_to_play": self.state.side_to_play,
                "is_priority": 0,
                "learned": self.state.learned,
                "needs_review": self.state.needs_review,
                "correct_streak": self.state.correct_streak,
                "priority_override": 0,
                "auto_priority_score": 0,
                "focus_max_ply": None,
            }
        if "INSERT INTO trainer_sessions" in query:
            sid, line_id, mode = args
            row = {
                "id": sid,
                "line_id": line_id,
                "mode": mode,
                "player_move_index": 0,
                "had_incorrect": 0,
                "completed": 0,
            }
            self.sessions[sid] = row
            return {"id": sid}
        if "FROM trainer_sessions" in query:
            sid = args[0]
            return self.sessions.get(sid)
        if "COUNT(*) FILTER" in query:
            return {"remaining": 1 if self.state.learned == 0 else 0, "learned": self.state.learned, "needs_review": self.state.needs_review}
        if "SELECT learned, needs_review" in query:
            return {"learned": self.state.learned, "needs_review": self.state.needs_review}
        return None


class _Acquire:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        return _Acquire(self._conn)


class _Request:
    def __init__(self, conn: _FakeConn):
        self.app = types.SimpleNamespace(state=types.SimpleNamespace(db_pool=_Pool(conn)))


def test_trainer_session_create_and_completion(monkeypatch) -> None:
    class _Settings:
        data_backend = "postgres"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakeConn()
    request = _Request(conn)

    session = asyncio.run(
        api_service.create_trainer_session(
            api_service.TrainerSessionCreateRequest(mode="learn", line_id="line-1"),
            request=request,
            _="dev-user",
        )
    )

    assert session.item.branch_id == "line-1"
    assert session.queue_snapshot.remaining == 1

    result1 = asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(move_uci="e2e4", elapsed_ms=50),
            request=request,
            _="dev-user",
        )
    )
    assert result1.outcome == "correct"
    assert result1.grade == "good"
    assert result1.next_item is not None

    result2 = asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(move_uci="g1f3", elapsed_ms=80),
            request=request,
            _="dev-user",
        )
    )
    assert result2.outcome == "correct"
    assert result2.grade == "easy"
    assert result2.item_state == "learned"
    assert result2.next_item is None


def test_trainer_session_incorrect_marks_review_and_remediation(monkeypatch) -> None:
    class _Settings:
        data_backend = "postgres"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakeConn()
    request = _Request(conn)

    session = asyncio.run(
        api_service.create_trainer_session(
            api_service.TrainerSessionCreateRequest(mode="review", line_id="line-1"),
            request=request,
            _="dev-user",
        )
    )

    wrong = asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(move_uci="a2a3", elapsed_ms=10),
            request=request,
            _="dev-user",
        )
    )
    assert wrong.outcome == "incorrect"
    assert wrong.grade == "again"
    assert wrong.item_state == "needs_review"
    assert wrong.remediation is not None


def test_trainer_session_invalid_paths(monkeypatch) -> None:
    class _Settings:
        data_backend = "postgres"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakeConn()
    request = _Request(conn)

    try:
        asyncio.run(
            api_service.answer_trainer_session(
                "not-a-uuid",
                api_service.TrainerSessionAnswerRequest(move_uci="e2e4", elapsed_ms=12),
                request=request,
                _="dev-user",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail["error_code"] == "INVALID_SESSION_ID"
    else:
        raise AssertionError("Expected INVALID_SESSION_ID")

    try:
        api_service.TrainerSessionAnswerRequest(move_uci="e2", elapsed_ms=-1)
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected payload validation to fail")


def test_trainer_sessions_not_implemented_for_sqlite(monkeypatch) -> None:
    class _Settings:
        data_backend = "sqlite"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    conn = _FakeConn()
    request = _Request(conn)

    try:
        asyncio.run(
            api_service.create_trainer_session(
                api_service.TrainerSessionCreateRequest(mode="review", line_id="line-1"),
                request=request,
                _="dev-user",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 501
        assert exc.detail["error_code"] == "NOT_IMPLEMENTED"
    else:
        raise AssertionError("Expected NOT_IMPLEMENTED for sqlite backend")
