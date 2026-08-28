from __future__ import annotations

import asyncio
import sqlite3
import sys
import types

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


def _configure_sqlite_backend(monkeypatch) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    _seed(conn)

    class _Settings:
        data_backend = "sqlite"
        sqlite_path = ":memory:"

    monkeypatch.setattr(api_service, "SETTINGS", _Settings())
    monkeypatch.setattr(api_service, "_sqlite_runtime_conn", lambda: conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO positions (id, fen_norm, side_to_move) VALUES (?, ?, ?)",
        [
            (1, "startpos w", "w"),
            (2, "after-e4 b", "b"),
            (3, "after-d4 b", "b"),
            (4, "rep-only w", "w"),
            (5, "rep-only-next b", "b"),
            (99, "empty w", "w"),
        ],
    )
    conn.executemany(
        "INSERT INTO repertoire_lines (line_id, canonical_path_hash, side_to_play, is_priority) VALUES (?, ?, ?, ?)",
        [
            ("line-e4", "hash-e4", "white", 1),
            ("line-d4", "hash-d4", "white", 0),
            ("line-rep-only", "hash-rep-only", "white", 0),
        ],
    )
    conn.executemany(
        "INSERT INTO repertoire_compact (line_id, moves_json, san_moves_json, pos_ids_json, ply_count) VALUES (?, ?, ?, ?, ?)",
        [
            ("line-e4", '["e2e4"]', '["e4"]', "[1,2]", 1),
            ("line-d4", '["d2d4"]', '["d4"]', "[1,3]", 1),
            ("line-rep-only", '["g1f3"]', '["Nf3"]', "[4,5]", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO repertoire_edges (pos_id, uci_move, next_pos_id, weight, is_priority_edge, is_user_mainline) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "e2e4", 2, 3, 1, 1),
            (1, "d2d4", 3, 1, 0, 0),
            (4, "g1f3", 5, 1, 0, 0),
        ],
    )
    conn.executemany(
        """
        INSERT INTO games (id, pgn_hash, date, white, black, result, player_color, white_elo, black_elo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (10, "hash-game-10", "2024.02.01", "Me", "Opponent A", "1-0", "white", 1600, 1580),
            (11, "hash-game-11", "2024.01.01", "Me", "Opponent B", "0-1", "white", 1610, 1700),
        ],
    )
    conn.executemany(
        """
        INSERT INTO game_positions (game_id, ply, pos_id, san_move, uci_move, is_self, repertoire_class)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (10, 1, 1, "e4", "e2e4", 1, "in_main"),
            (11, 1, 1, "c4", "c2c4", 1, "out_rep"),
        ],
    )
    conn.executemany(
        "INSERT INTO matches (game_id, deviation_ply_opp, compliance, who_left_first) VALUES (?, ?, ?, ?)",
        [
            (10, None, "mainline", None),
            (11, 1, "deviation", "opponent"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO analysis_ply (game_id, ply, pos_id, post_eval_cp, your_cpl, rep_cpl, best_uci)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (10, 1, 1, 35, 12, 5, "e2e4"),
            (11, 1, 1, -80, 140, 20, "e2e4"),
        ],
    )
    conn.execute(
        "INSERT INTO engine_cache (pos_id, depth, engine_id, best_uci, eval_cp, analyzed_at) VALUES (1, 16, 'stockfish', 'e2e4', 22, '2024-01-01')"
    )
    conn.commit()


def test_position_intelligence_populated_position(monkeypatch) -> None:
    _configure_sqlite_backend(monkeypatch)

    payload = asyncio.run(api_service.get_position_intelligence(pos_id=1, request=None, _="dev-user"))

    assert payload.pos_id == 1
    assert payload.position["fen"] == "startpos w"
    assert [move.uci_move for move in payload.repertoire_continuations] == ["e2e4", "d2d4"]
    assert {move["uci_move"] for move in payload.game_continuations} == {"e2e4", "c2c4"}
    assert payload.coverage["coverage_pct"] == 50.0
    assert payload.coverage["played_non_repertoire_moves"] == 1
    assert payload.coverage["opponent_deviation_count"] == 1
    assert payload.outcome_summary["games"] == 2
    assert payload.evaluation_summary["best_uci"] == "e2e4"
    assert len(payload.recent_games) == 2
    assert payload.evidence["matters"]


def test_position_intelligence_repertoire_only_position(monkeypatch) -> None:
    _configure_sqlite_backend(monkeypatch)

    payload = asyncio.run(api_service.get_position_intelligence(pos_id=4, request=None, _="dev-user"))

    assert [move.uci_move for move in payload.repertoire_continuations] == ["g1f3"]
    assert payload.game_continuations == []
    assert payload.coverage["total_repertoire_moves"] == 1
    assert payload.coverage["covered_by_games"] == 0
    assert payload.outcome_summary["games"] == 0
    assert payload.recent_games == []


def test_position_intelligence_empty_position(monkeypatch) -> None:
    _configure_sqlite_backend(monkeypatch)

    payload = asyncio.run(api_service.get_position_intelligence(pos_id=99, request=None, _="dev-user"))

    assert payload.position["fen"] == "empty w"
    assert payload.repertoire_continuations == []
    assert payload.game_continuations == []
    assert payload.coverage["coverage_pct"] == 0.0
    assert payload.outcome_summary["games"] == 0
    assert payload.evidence["matters"] == []
