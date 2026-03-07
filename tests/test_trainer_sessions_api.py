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
        if "SET learned = 1" in query and "times_incorrect = times_incorrect + 1" in query:
            self.state.learned = 1
            self.state.needs_review = 1
            self.state.correct_streak = 0
            self.state.times_incorrect += 1
            return "UPDATE 1"
        if "SET learned = 1" in query and "times_correct = times_correct + 1" in query:
            self.state.learned = 1
            self.state.needs_review = 0
            self.state.correct_streak = int(args[1])
            self.state.times_correct += 1
            return "UPDATE 1"
        return "OK"

    async def fetch(self, query: str, *args):
        if "FROM line_positions" in query:
            return [
                {"ply": 1, "san_move": "e4", "uci_move": "e2e4", "pos_id": 1, "next_pos_id": 2},
                {"ply": 2, "san_move": "e5", "uci_move": "e7e5", "pos_id": 2, "next_pos_id": 3},
                {"ply": 3, "san_move": "Nf3", "uci_move": "g1f3", "pos_id": 3, "next_pos_id": 4},
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
            return row
        if "FROM trainer_sessions" in query:
            sid = args[0]
            return self.sessions.get(sid)
        if "SELECT line_id, learned, needs_review" in query:
            return {
                "line_id": "line-1",
                "learned": self.state.learned,
                "needs_review": self.state.needs_review,
                "correct_streak": self.state.correct_streak,
                "times_correct": self.state.times_correct,
                "times_incorrect": self.state.times_incorrect,
            }
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


def test_trainer_session_correct_updates_counters(monkeypatch) -> None:
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

    asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(answer_uci="e2e4"),
            request=request,
            _="dev-user",
        )
    )
    final = asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(answer_uci="g1f3"),
            request=request,
            _="dev-user",
        )
    )

    assert final.completed is True
    assert final.learned == 1
    assert final.needs_review == 0
    assert final.correct_streak == 1
    assert final.times_correct == 1


def test_trainer_session_incorrect_marks_needs_review(monkeypatch) -> None:
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
            api_service.TrainerSessionAnswerRequest(answer_uci="a2a3"),
            request=request,
            _="dev-user",
        )
    )
    assert wrong.next_step.phase == "reveal_explanation"

    asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(answer_uci="e2e4"),
            request=request,
            _="dev-user",
        )
    )
    final = asyncio.run(
        api_service.answer_trainer_session(
            session.session_id,
            api_service.TrainerSessionAnswerRequest(answer_uci="g1f3"),
            request=request,
            _="dev-user",
        )
    )

    assert final.completed is True
    assert final.needs_review == 1
    assert final.correct_streak == 0
    assert final.times_incorrect == 1


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
