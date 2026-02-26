from __future__ import annotations

import concurrent.futures
import hashlib
import json
import multiprocessing
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import chess
import chess.engine
import chess.pgn

from analysis import compliance, matching, propositions, review
from analysis import insights as insights_module
from analysis.engine_cache import analyze_position, engine_identity
from analysis import engine_parallel
from analysis.position_utils import material_key, normalize_fen, zobrist_hash
from analysis.thresholds import (
    BEST_MAX,
    BLUNDER_CLUSTER_WINDOW,
    BLUNDER_MIN,
    EXCELLENT_MAX,
    INSTANT_OUT_OF_BOOK_MAX_PLY,
    INACCURACY_MIN,
    MISTAKE_MIN,
    SLOW_IN_BOOK_PCT,
)
from parsing import clock_parser, game_loader, repertoire_loader
from storage import queries

PROGRESS_EMIT_SECONDS = 0.5
PROGRESS_EMIT_POSITIONS = 250


class PositionStore:
    def __init__(self, conn):
        self.conn = conn
        self.cache: dict[str, int] = {}

    def get_or_create(self, board: chess.Board) -> int:
        fen_norm = normalize_fen(board)
        if fen_norm in self.cache:
            return self.cache[fen_norm]

        row = self.conn.execute(
            "SELECT id FROM positions WHERE fen_norm = ?", (fen_norm,)
        ).fetchone()
        if row:
            pos_id = int(row["id"])
            self.cache[fen_norm] = pos_id
            return pos_id

        z_hash = zobrist_hash(board)
        mat_key = material_key(board)
        side = "w" if board.turn == chess.WHITE else "b"
        cursor = self.conn.execute(
            """
            INSERT INTO positions (fen_norm, zobrist, material_key, side_to_move)
            VALUES (?, ?, ?, ?)
            """,
            (fen_norm, z_hash, mat_key, side),
        )
        self.conn.commit()
        pos_id = int(cursor.lastrowid)
        self.cache[fen_norm] = pos_id
        return pos_id


def _emit_progress(
    progress_cb: Callable[[dict], None] | None,
    phase: str,
    **data,
) -> None:
    if not progress_cb:
        return
    payload = {"phase": phase}
    payload.update(data)
    try:
        progress_cb(payload)
    except Exception:
        pass


def _effective_engine_id(base_engine_id: str, config) -> str:
    mode = (config.engine_mode or "fixed").strip().lower()
    if mode == "adaptive":
        mode_key = f"adaptive:{int(config.engine_max_time_ms)}ms"
    else:
        mode_key = "fixed"
    return f"{base_engine_id}|mode={mode_key}|depth={int(config.engine_depth)}"


def _prune_non_active_engine_cache(
    conn,
    active_depth: int,
    active_engine_id: str,
    enabled: bool,
) -> None:
    if not enabled:
        return
    conn.execute(
        """
        DELETE FROM engine_cache
        WHERE depth != ? OR engine_id != ?
        """,
        (active_depth, active_engine_id),
    )
    conn.commit()


def _force_cleanup_executor_processes(executor) -> None:
    raw_processes = getattr(executor, "_processes", None)
    if isinstance(raw_processes, dict):
        processes = list(raw_processes.values())
    else:
        processes = []
    if not processes:
        return
    if os.name == "nt":
        for process in processes:
            pid = getattr(process, "pid", None)
            if not pid:
                continue
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
        return
    for process in processes:
        try:
            process.terminate()
        except Exception:
            pass


def _compute_file_hash(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _list_pgn_files(root: Path) -> list[Path]:
    return sorted({*root.rglob("*.pgn"), *root.rglob("*.PGN")})


def _load_source_files(conn, file_type: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT path, file_hash FROM source_files WHERE file_type = ?", (file_type,)
    ).fetchall()
    return {row["path"]: row["file_hash"] for row in rows}


def _update_source_files(conn, file_type: str, files: dict[str, str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM source_files WHERE file_type = ?", (file_type,))
    rows = [(path, file_hash, file_type, now) for path, file_hash in files.items()]
    conn.executemany(
        """
        INSERT INTO source_files (path, file_hash, file_type, last_seen)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def _clear_data(conn) -> None:
    conn.executescript(
        """
        DELETE FROM review_items;
        DELETE FROM insights;
        DELETE FROM branch_queue;
        DELETE FROM review_propositions;
        DELETE FROM analysis_ply;
        DELETE FROM time_patterns;
        DELETE FROM engine_cache;
        DELETE FROM matches;
        DELETE FROM game_positions;
        DELETE FROM games;
        DELETE FROM trainer_line_state;
        DELETE FROM repertoire_edges;
        DELETE FROM repertoire_compact;
        DELETE FROM repertoire_lines;
        DELETE FROM user_mainline_overrides;
        DELETE FROM positions;
        DELETE FROM source_files;
        """
    )
    conn.commit()


def _insert_repertoire_lines(
    conn, position_store: PositionStore, lines: list[dict]
) -> None:
    for line in lines:
        conn.execute(
            """
            INSERT OR REPLACE INTO repertoire_lines (
                line_id, source_pgn, is_priority, side_to_play
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                line["line_id"],
                line.get("source_pgn"),
                1 if line.get("is_priority") else 0,
                line.get("side_to_play") or "white",
            ),
        )

        board = chess.Board()
        moves_uci: list[str] = []
        san_moves: list[str] = []
        pos_ids: list[int] = []
        for move in line["moves"]:
            pos_ids.append(position_store.get_or_create(board))
            chess_move = chess.Move.from_uci(move["uci"])
            board.push(chess_move)
            moves_uci.append(move.get("uci") or "")
            san_moves.append(move.get("san") or "")
        pos_ids.append(position_store.get_or_create(board))
        conn.execute(
            """
            INSERT OR REPLACE INTO repertoire_compact
                (line_id, moves_json, san_moves_json, pos_ids_json, ply_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                line["line_id"],
                json.dumps(moves_uci),
                json.dumps(san_moves),
                json.dumps(pos_ids),
                len(moves_uci),
            ),
        )
    conn.commit()


def _build_repertoire_edges(conn) -> None:
    conn.execute("DELETE FROM repertoire_edges")
    rows = conn.execute(
        """
        SELECT lp.pos_id, lp.uci_move, lp.next_pos_id, lp.line_id, rl.is_priority
        FROM line_positions lp
        JOIN repertoire_lines rl ON lp.line_id = rl.line_id
        """
    ).fetchall()

    edges: dict[tuple[int, str, int], dict] = {}
    for row in rows:
        key = (row["pos_id"], row["uci_move"], row["next_pos_id"])
        entry = edges.setdefault(
            key, {"weight": 0, "sources": set(), "is_priority": 0}
        )
        entry["weight"] += 1
        entry["sources"].add(row["line_id"])
        if row["is_priority"]:
            entry["is_priority"] = 1

    insert_rows = []
    for (pos_id, uci_move, next_pos_id), entry in edges.items():
        insert_rows.append(
            (
                pos_id,
                uci_move,
                next_pos_id,
                entry["weight"],
                json.dumps(sorted(entry["sources"])),
                entry["is_priority"],
            )
        )

    conn.executemany(
        """
        INSERT INTO repertoire_edges (
            pos_id, uci_move, next_pos_id, weight, sources_json, is_priority_edge
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        insert_rows,
    )
    conn.commit()


def _ensure_trainer_state(conn) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO trainer_line_state (line_id, side_to_play)
        SELECT line_id, COALESCE(side_to_play, 'white')
        FROM repertoire_lines
        """
    )
    conn.execute(
        """
        UPDATE trainer_line_state
        SET side_to_play = (
            SELECT COALESCE(rl.side_to_play, 'white')
            FROM repertoire_lines rl
            WHERE rl.line_id = trainer_line_state.line_id
        )
        WHERE line_id IN (SELECT line_id FROM repertoire_lines)
        """
    )
    conn.commit()

    overrides = conn.execute(
        "SELECT pos_id, uci_move, next_pos_id FROM user_mainline_overrides"
    ).fetchall()
    for row in overrides:
        conn.execute(
            """
            UPDATE repertoire_edges
            SET is_user_mainline = 1
            WHERE pos_id = ? AND uci_move = ? AND next_pos_id = ?
            """,
            (row["pos_id"], row["uci_move"], row["next_pos_id"]),
        )
    conn.commit()


def _build_line_indexes(
    line_data: list[dict],
) -> tuple[dict[str, list[str]], dict[tuple[str, ...], list[str]], dict[tuple[int, ...], list[str]]]:
    line_moves_map: dict[str, list[str]] = {}
    move_prefix_map: dict[tuple[str, ...], list[str]] = {}
    pos_prefix_map: dict[tuple[int, ...], list[str]] = {}

    for line in line_data:
        line_id = line["line_id"]
        moves = line["moves_uci"]
        pos_ids = line["pos_ids"]
        line_moves_map[line_id] = moves
        for idx in range(1, len(moves) + 1):
            move_prefix = tuple(moves[:idx])
            pos_prefix = tuple(pos_ids[:idx])
            move_prefix_map.setdefault(move_prefix, []).append(line_id)
            pos_prefix_map.setdefault(pos_prefix, []).append(line_id)

    return line_moves_map, move_prefix_map, pos_prefix_map


def _canonical_line_from_prefix(
    context: dict | None,
    max_matched_ply: int | None,
    matching_mode: str | None,
    move_prefix_map: dict[tuple[str, ...], list[str]],
    pos_prefix_map: dict[tuple[int, ...], list[str]],
) -> str | None:
    if not context:
        return None
    max_matched = int(max_matched_ply or 0)
    if max_matched <= 0:
        return None

    mode = (matching_mode or "STRICT").upper()
    if mode == "TRANSPOSITION":
        prefix = tuple(context["pos_ids"][:max_matched])
        candidates = pos_prefix_map.get(prefix, [])
    else:
        prefix = tuple(context["moves_uci"][:max_matched])
        candidates = move_prefix_map.get(prefix, [])
    if not candidates:
        return None
    return min(candidates)


def _attach_effective_matched_lines(
    conn,
    games: list[dict],
    line_data: list[dict],
    matching_mode: str,
    runtime_line_ids: dict[int, str | None] | None = None,
) -> None:
    if not games:
        return

    _line_moves_map, move_prefix_map, pos_prefix_map = _build_line_indexes(line_data)
    runtime_line_ids = runtime_line_ids or {}

    game_ids = [int(game["game_id"]) for game in games]
    placeholders = ",".join("?" for _ in game_ids)
    rows = conn.execute(
        f"""
        SELECT game_id, matched_line_id, matching_mode, max_matched_ply
        FROM matches
        WHERE game_id IN ({placeholders})
        """,
        tuple(game_ids),
    ).fetchall()
    match_map = {int(row["game_id"]): row for row in rows}

    for game in games:
        game_id = int(game["game_id"])
        runtime_line = runtime_line_ids.get(game_id)
        if runtime_line:
            game["matched_line_id"] = runtime_line
            continue

        row = match_map.get(game_id)
        stored_line = row["matched_line_id"] if row else None
        if stored_line:
            game["matched_line_id"] = stored_line
            continue

        mode = row["matching_mode"] if row and row["matching_mode"] else matching_mode
        max_matched_ply = row["max_matched_ply"] if row else 0
        game["matched_line_id"] = _canonical_line_from_prefix(
            game, max_matched_ply, mode, move_prefix_map, pos_prefix_map
        )


def _enforce_match_storage_policy(conn) -> None:
    conn.execute("UPDATE matches SET tie_lines_json = NULL WHERE tie_lines_json IS NOT NULL")
    conn.execute(
        """
        UPDATE matches
        SET matched_line_id = NULL
        WHERE compliance <> 'FULLY_COMPLIANT' AND matched_line_id IS NOT NULL
        """
    )
    conn.commit()


def _apply_game_based_trainer_priority(
    conn,
    runtime_line_ids: dict[int, str | None] | None = None,
    min_matched_plies: int = 3,
) -> None:
    line_data = _load_line_data(conn)
    line_moves_map, move_prefix_map, pos_prefix_map = _build_line_indexes(line_data)
    game_context_map = {ctx["game_id"]: ctx for ctx in _load_game_contexts(conn)}
    runtime_line_ids = runtime_line_ids or {}

    conn.execute(
        "UPDATE trainer_line_state SET auto_priority_score = 0, focus_max_ply = NULL"
    )
    conn.commit()

    matches = conn.execute(
        """
        SELECT game_id, matched_line_id, matching_mode, max_matched_ply, deviation_ply_you, compliance
        FROM matches
        """
    ).fetchall()

    min_ply = max(0, int(min_matched_plies or 0))
    for row in matches:
        max_matched = row["max_matched_ply"] or 0
        if max_matched < min_ply:
            continue
        if row["compliance"] == "INCOMPLETE" and max_matched < 10:
            continue

        game_id = int(row["game_id"])
        line_id = runtime_line_ids.get(game_id)
        if not line_id:
            line_id = row["matched_line_id"]
        if not line_id:
            line_id = _canonical_line_from_prefix(
                game_context_map.get(game_id),
                row["max_matched_ply"],
                row["matching_mode"],
                move_prefix_map,
                pos_prefix_map,
            )
        if not line_id:
            continue

        conn.execute(
            "UPDATE trainer_line_state SET auto_priority_score = auto_priority_score + 1 WHERE line_id = ?",
            (line_id,),
        )

        deviation_ply = row["deviation_ply_you"]
        if not deviation_ply:
            continue

        if max_matched >= 10:
            edge = conn.execute(
                """
                SELECT pos_id, uci_move, next_pos_id
                FROM line_positions
                WHERE line_id = ? AND ply = ?
                """,
                (line_id, deviation_ply),
            ).fetchone()
            if edge:
                conn.execute(
                    "DELETE FROM user_mainline_overrides WHERE pos_id = ?",
                    (edge["pos_id"],),
                )
                conn.execute(
                    """
                    INSERT INTO user_mainline_overrides (pos_id, uci_move, next_pos_id)
                    VALUES (?, ?, ?)
                    """,
                    (edge["pos_id"], edge["uci_move"], edge["next_pos_id"]),
                )
                conn.execute(
                    """
                    UPDATE repertoire_edges
                    SET is_user_mainline = CASE
                        WHEN pos_id = ? AND uci_move = ? AND next_pos_id = ? THEN 1
                        ELSE 0
                    END
                    WHERE pos_id = ?
                    """,
                    (
                        edge["pos_id"],
                        edge["uci_move"],
                        edge["next_pos_id"],
                        edge["pos_id"],
                    ),
                )

            moves = line_moves_map.get(line_id, [])
            prefix = tuple(moves[:deviation_ply])
            for branch_line in move_prefix_map.get(prefix, []):
                conn.execute(
                    """
                    UPDATE trainer_line_state
                    SET auto_priority_score = auto_priority_score + 1,
                        focus_max_ply = NULL
                    WHERE line_id = ?
                    """,
                    (branch_line,),
                )
        else:
            focus_ply = deviation_ply + 2
            conn.execute(
                """
                UPDATE trainer_line_state
                SET focus_max_ply = CASE
                    WHEN focus_max_ply IS NULL THEN ?
                    WHEN focus_max_ply < ? THEN ?
                    ELSE focus_max_ply
                END
                WHERE line_id = ?
                """,
                (focus_ply, focus_ply, focus_ply, line_id),
            )

    conn.commit()


def _insert_games(
    conn,
    position_store: PositionStore,
    games: list[dict],
) -> list[dict]:
    contexts_by_hash: dict[str, dict] = {}
    duplicate_hash_count = 0
    for game in games:
        tags = game["tags"]
        moves_uci = game["moves_uci"]
        pgn_hash = queries.compute_game_hash(tags, moves_uci)

        game_record = {
            "pgn_hash": pgn_hash,
            "source_pgn": game.get("source_pgn"),
            "event": tags.get("Event"),
            "site": tags.get("Site"),
            "date": game.get("date"),
            "utc_date": tags.get("UTCDate"),
            "utc_time": tags.get("UTCTime"),
            "white": tags.get("White"),
            "black": tags.get("Black"),
            "result": tags.get("Result"),
            "time_control": game.get("time_control"),
            "white_elo": _safe_int(tags.get("WhiteElo")),
            "black_elo": _safe_int(tags.get("BlackElo")),
            "player_color": game.get("player_color"),
            "is_daily": game.get("is_daily"),
            "termination": tags.get("Termination"),
            "eco": tags.get("ECO"),
        }

        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO games (
                pgn_hash, source_pgn, event, site, date, utc_date, utc_time, white,
                black, result, time_control, white_elo, black_elo, player_color, is_daily,
                termination, eco
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_record["pgn_hash"],
                game_record["source_pgn"],
                game_record["event"],
                game_record["site"],
                game_record["date"],
                game_record["utc_date"],
                game_record["utc_time"],
                game_record["white"],
                game_record["black"],
                game_record["result"],
                game_record["time_control"],
                game_record["white_elo"],
                game_record["black_elo"],
                game_record["player_color"],
                1 if game_record["is_daily"] else 0,
                game_record["termination"],
                game_record["eco"],
            ),
        )
        game_id = int(cursor.lastrowid)

        board = chess.Board()
        pos_ids: list[int] = []
        for move in game["moves"]:
            pos_id = position_store.get_or_create(board)
            pos_ids.append(pos_id)
            chess_move = chess.Move.from_uci(move["move_uci"])
            board.push(chess_move)

        base_seconds, _ = clock_parser.parse_time_control(game_record["time_control"])
        for idx, move in enumerate(game["moves"], start=1):
            time_spent = move.get("time_spent_seconds")
            fraction = None
            if base_seconds and time_spent is not None:
                fraction = time_spent / base_seconds
            conn.execute(
                """
                INSERT OR REPLACE INTO game_positions (
                    game_id, ply, pos_id, san_move, uci_move, clock_seconds,
                    time_spent_seconds, time_spent_fraction, is_self, repertoire_class
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    game_id,
                    idx,
                    pos_ids[idx - 1],
                    move.get("move_san"),
                    move.get("move_uci"),
                    move.get("clock_seconds"),
                    time_spent,
                    fraction,
                    1 if move.get("is_self") else 0,
                ),
            )

        if pgn_hash in contexts_by_hash:
            duplicate_hash_count += 1
        contexts_by_hash[pgn_hash] = {
            "game_id": game_id,
            "moves_uci": moves_uci,
            "pos_ids": pos_ids,
            "player_color": game.get("player_color"),
            "date": game.get("date") or "",
        }

    conn.commit()
    if duplicate_hash_count:
        print(f"Skipped {duplicate_hash_count} duplicate game contexts by pgn_hash.")
    return list(contexts_by_hash.values())


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _load_line_data(conn) -> list[dict]:
    line_moves: dict[str, list[str]] = {}
    line_pos_ids: dict[str, list[int]] = {}

    rows = conn.execute(
        """
        SELECT line_id, ply, uci_move, pos_id
        FROM line_positions
        ORDER BY line_id, ply
        """
    ).fetchall()

    for row in rows:
        line_moves.setdefault(row["line_id"], []).append(row["uci_move"])
        line_pos_ids.setdefault(row["line_id"], []).append(int(row["pos_id"]))

    return [
        {
            "line_id": line_id,
            "moves_uci": line_moves.get(line_id, []),
            "pos_ids": line_pos_ids.get(line_id, []),
        }
        for line_id in line_moves
    ]


def _load_game_contexts(conn, game_ids: list[int] | None = None) -> list[dict]:
    contexts: list[dict] = []
    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"WHERE g.id IN ({placeholders})"
        params = list(game_ids)

    games = conn.execute(
        f"""
        SELECT g.id, g.player_color, g.date
        FROM games g
        {clause}
        """,
        params,
    ).fetchall()

    for game in games:
        rows = conn.execute(
            """
            SELECT ply, pos_id, uci_move
            FROM game_positions
            WHERE game_id = ?
            ORDER BY ply
            """,
            (game["id"],),
        ).fetchall()
        moves_uci = [row["uci_move"] for row in rows]
        pos_ids = [int(row["pos_id"]) for row in rows]
        contexts.append(
            {
                "game_id": game["id"],
                "moves_uci": moves_uci,
                "pos_ids": pos_ids,
                "player_color": game["player_color"],
                "date": game["date"] or "",
            }
        )

    return contexts


def _load_match_metadata(
    conn, game_ids: list[int] | None = None
) -> dict[int, dict]:
    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"WHERE game_id IN ({placeholders})"
        params = list(game_ids)
    rows = conn.execute(
        f"""
        SELECT game_id, compliance, deviation_ply_you
        FROM matches
        {clause}
        """,
        params,
    ).fetchall()
    return {
        int(row["game_id"]): {
            "compliance": row["compliance"],
            "deviation_ply_you": row["deviation_ply_you"],
        }
        for row in rows
    }


def _load_edge_map(conn) -> dict[int, set[str]]:
    rows = conn.execute(
        "SELECT pos_id, uci_move FROM repertoire_edges"
    ).fetchall()
    edge_map: dict[int, set[str]] = {}
    for row in rows:
        edge_map.setdefault(int(row["pos_id"]), set()).add(row["uci_move"])
    return edge_map


def _load_repertoire_positions(conn) -> set[int]:
    rows = conn.execute(
        "SELECT DISTINCT pos_id FROM line_positions"
    ).fetchall()
    return {int(row["pos_id"]) for row in rows}


def _classify_quality(cpl: int | None) -> str | None:
    if cpl is None:
        return None
    if cpl <= BEST_MAX:
        return "BEST"
    if cpl <= EXCELLENT_MAX:
        return "EXCELLENT"
    if cpl >= BLUNDER_MIN:
        return "BLUNDER"
    if cpl >= MISTAKE_MIN:
        return "MISTAKE"
    if cpl >= INACCURACY_MIN:
        return "INACCURACY"
    return "GOOD"


def _pov_eval(eval_cp: int | None, player_color: str) -> int | None:
    if eval_cp is None:
        return None
    return eval_cp if player_color == "white" else -eval_cp


def _update_game_classification(
    conn,
    game_context: dict,
    line_moves: list[str],
    line_pos_ids: list[int],
    edge_map: dict[int, set[str]],
    repertoire_positions: set[int],
) -> tuple[dict, list[str]]:
    game_id = game_context["game_id"]
    moves_uci = game_context["moves_uci"]
    pos_ids = game_context["pos_ids"]
    player_color = game_context["player_color"]

    out_of_rep_started = False
    recovered = False
    opponent_dev_to_known = False
    first_out_ply = None

    updates = []
    for idx, move in enumerate(moves_uci, start=1):
        pos_id = pos_ids[idx - 1]
        rep_moves = edge_map.get(pos_id, set())
        line_move = line_moves[idx - 1] if idx - 1 < len(line_moves) else None
        line_pos_id = line_pos_ids[idx - 1] if idx - 1 < len(line_pos_ids) else None
        if move in rep_moves:
            if line_move and move == line_move and line_pos_id == pos_id:
                rep_class = "IN_REPERTOIRE_MAIN"
            else:
                rep_class = "IN_REPERTOIRE_OTHER"
        else:
            rep_class = "OUT_OF_REPERTOIRE"
        updates.append((rep_class, game_id, idx))

        if rep_class == "OUT_OF_REPERTOIRE" and not out_of_rep_started:
            out_of_rep_started = True
            first_out_ply = idx
        if out_of_rep_started and pos_id in repertoire_positions:
            recovered = True

    conn.executemany(
        """
        UPDATE game_positions
        SET repertoire_class = ?
        WHERE game_id = ? AND ply = ?
        """,
        updates,
    )

    if first_out_ply is not None:
        mover_is_white = (first_out_ply % 2) == 1
        opponent_move = (player_color == "white" and not mover_is_white) or (
            player_color == "black" and mover_is_white
        )
        if opponent_move:
            next_index = first_out_ply
            if next_index < len(pos_ids):
                pos_after = pos_ids[next_index]
                if pos_after in repertoire_positions:
                    opponent_dev_to_known = True

    return {
        "recovered_to_rep": recovered,
        "opponent_dev_to_known": opponent_dev_to_known,
        "first_out_ply": first_out_ply,
    }, updates


def _compute_worker_count(config) -> int:
    if config.engine_workers and config.engine_workers > 0:
        return int(config.engine_workers)
    threads = max(1, int(config.engine_threads or 1))
    cpu_count = os.cpu_count() or 1
    profile = (config.engine_profile or "manual").strip().lower()

    if profile == "aggressive":
        target = max(1, cpu_count - 2)
        workers = max(1, target // threads)
    elif profile == "balanced":
        target = max(1, int(round(cpu_count * 0.65)))
        workers = max(1, target // threads)
    elif profile == "conservative":
        target = max(1, int(round(cpu_count * 0.50)))
        workers = max(1, target // threads)
    else:
        workers = max(1, cpu_count // threads)
        cap = int(config.engine_worker_cap or 1)
        if cap > 0:
            workers = min(workers, cap)
    return max(1, min(workers, cpu_count))


def _build_engine_cache(
    conn,
    engine,
    position_store: PositionStore,
    games: list[dict],
    depth: int,
    engine_id: str,
    enable_cache: bool,
    config,
    progress_cb: Callable[[dict], None] | None = None,
) -> dict[int, dict]:
    _emit_progress(
        progress_cb,
        "Preparing positions",
        done=0,
        total=0,
        workers=0,
        mode=config.engine_mode,
        depth=depth,
    )
    cache_map: dict[int, dict] = {}
    if enable_cache and config.engine_cache_prune_non_active:
        _prune_non_active_engine_cache(
            conn,
            active_depth=depth,
            active_engine_id=engine_id,
            enabled=True,
        )

    if enable_cache:
        rows = conn.execute(
            """
            SELECT pos_id, best_uci, eval_cp, wdl_json
            FROM engine_cache
            WHERE depth = ? AND engine_id = ?
            """,
            (depth, engine_id),
        ).fetchall()
        for row in rows:
            cache_map[int(row["pos_id"])] = {
                "best_uci": row["best_uci"],
                "eval_cp": row["eval_cp"],
                "wdl_json": row["wdl_json"],
            }

    missing: dict[int, str] = {}
    total_positions = 0
    for game in games:
        board = chess.Board()
        for move_uci in game["moves_uci"]:
            pos_id = position_store.get_or_create(board)
            total_positions += 1
            if pos_id not in cache_map and pos_id not in missing:
                missing[pos_id] = board.fen()

            move = chess.Move.from_uci(move_uci)
            board.push(move)
            post_id = position_store.get_or_create(board)
            total_positions += 1
            if post_id not in cache_map and post_id not in missing:
                missing[post_id] = board.fen()

    new_entries: dict[int, dict] = {}
    if missing:
        workers = _compute_worker_count(config)
        completed = 0
        total_missing = len(missing)
        start_ts = time.time()
        last_emit_ts = 0.0
        _emit_progress(
            progress_cb,
            "Engine evaluation",
            done=completed,
            total=total_missing,
            speed=0.0,
            eta_seconds=0,
            workers=workers,
            mode=config.engine_mode,
            depth=depth,
            max_time_ms=config.engine_max_time_ms,
            cache_hits=max(0, total_positions - total_missing),
        )
        if workers > 1:
            tasks = [(pos_id, fen, depth) for pos_id, fen in missing.items()]
            ctx = multiprocessing.get_context("spawn")
            executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=workers,
                mp_context=ctx,
                initializer=engine_parallel.init_worker,
                initargs=(
                    config.stockfish_path,
                    config.engine_threads,
                    config.engine_hash_mb,
                    config.engine_mode,
                    config.engine_max_time_ms,
                ),
            )
            try:
                for pos_id, best_uci, eval_cp, wdl in executor.map(
                    engine_parallel.analyze_fen_task, tasks, chunksize=32
                ):
                    entry = {
                        "best_uci": best_uci,
                        "eval_cp": eval_cp,
                        "wdl_json": json.dumps(wdl) if wdl else None,
                    }
                    new_entries[pos_id] = entry
                    cache_map[pos_id] = entry
                    completed += 1
                    now = time.time()
                    if (
                        completed == total_missing
                        or completed % PROGRESS_EMIT_POSITIONS == 0
                        or now - last_emit_ts >= PROGRESS_EMIT_SECONDS
                    ):
                        elapsed = max(0.001, now - start_ts)
                        speed = completed / elapsed
                        remaining = max(0, total_missing - completed)
                        eta = int(remaining / speed) if speed > 0 else 0
                        _emit_progress(
                            progress_cb,
                            "Engine evaluation",
                            done=completed,
                            total=total_missing,
                            speed=speed,
                            eta_seconds=eta,
                            workers=workers,
                            mode=config.engine_mode,
                            depth=depth,
                            max_time_ms=config.engine_max_time_ms,
                            cache_hits=max(0, total_positions - total_missing),
                        )
                        last_emit_ts = now
            finally:
                _emit_progress(
                    progress_cb,
                    "Finalizing workers",
                    done=completed,
                    total=total_missing,
                    workers=workers,
                    mode=config.engine_mode,
                    depth=depth,
                )
                # Do not block UI on executor teardown; force cleanup worker trees.
                executor.shutdown(wait=False, cancel_futures=True)
                _force_cleanup_executor_processes(executor)
        else:
            for pos_id, fen in missing.items():
                board = chess.Board(fen)
                best_uci, eval_cp, wdl = analyze_position(
                    engine,
                    board,
                    depth,
                    mode=config.engine_mode,
                    max_time_ms=config.engine_max_time_ms,
                )
                entry = {
                    "best_uci": best_uci,
                    "eval_cp": eval_cp,
                    "wdl_json": json.dumps(wdl) if wdl else None,
                }
                new_entries[pos_id] = entry
                cache_map[pos_id] = entry
                completed += 1
                now = time.time()
                if (
                    completed == total_missing
                    or completed % PROGRESS_EMIT_POSITIONS == 0
                    or now - last_emit_ts >= PROGRESS_EMIT_SECONDS
                ):
                    elapsed = max(0.001, now - start_ts)
                    speed = completed / elapsed
                    remaining = max(0, total_missing - completed)
                    eta = int(remaining / speed) if speed > 0 else 0
                    _emit_progress(
                        progress_cb,
                        "Engine evaluation",
                        done=completed,
                        total=total_missing,
                        speed=speed,
                        eta_seconds=eta,
                        workers=workers,
                        mode=config.engine_mode,
                        depth=depth,
                        max_time_ms=config.engine_max_time_ms,
                        cache_hits=max(0, total_positions - total_missing),
                    )
                    last_emit_ts = now

    if enable_cache and new_entries:
        _emit_progress(
            progress_cb,
            "Writing cache",
            done=len(new_entries),
            total=len(new_entries),
            workers=_compute_worker_count(config),
            mode=config.engine_mode,
            depth=depth,
        )
        rows = []
        now = datetime.now(timezone.utc).isoformat()
        for pos_id, data in new_entries.items():
            rows.append(
                (
                    pos_id,
                    depth,
                    engine_id,
                    data.get("best_uci"),
                    data.get("eval_cp"),
                    data.get("wdl_json"),
                    now,
                )
            )
        conn.executemany(
            """
            INSERT OR REPLACE INTO engine_cache (
                pos_id, depth, engine_id, best_uci, eval_cp, wdl_json, analyzed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    elif not missing:
        _emit_progress(
            progress_cb,
            "Engine evaluation",
            done=0,
            total=0,
            speed=0.0,
            eta_seconds=0,
            workers=_compute_worker_count(config),
            mode=config.engine_mode,
            depth=depth,
            max_time_ms=config.engine_max_time_ms,
            cache_hits=total_positions,
        )

    return cache_map


def _compute_analysis_ply(
    conn,
    position_store: PositionStore,
    games: list[dict],
    cache_map: dict[int, dict],
    lines_by_id: dict[str, list[str]],
) -> None:
    if not games:
        return
    game_ids = [int(game["game_id"]) for game in games]
    match_meta = _load_match_metadata(conn, game_ids)
    rows = []
    for game in games:
        game_id = game["game_id"]
        player_color = game["player_color"]
        line_moves = lines_by_id.get(game.get("matched_line_id") or "", [])
        game_match = match_meta.get(int(game_id), {})
        game_compliance = str(game_match.get("compliance") or "")
        game_deviation_ply = game_match.get("deviation_ply_you")
        try:
            game_deviation_ply_int = int(game_deviation_ply or 0)
        except (TypeError, ValueError):
            game_deviation_ply_int = 0
        allow_rep_cpl = (
            game_compliance == "YOU_DEVIATED" and game_deviation_ply_int > 0
        )

        board = chess.Board()
        for ply_index, move_uci in enumerate(game["moves_uci"], start=1):
            pre_board = board.copy(stack=False)
            pos_id = position_store.get_or_create(pre_board)
            pre_eval_cp = cache_map.get(pos_id, {}).get("eval_cp")
            best_uci = cache_map.get(pos_id, {}).get("best_uci")

            move = chess.Move.from_uci(move_uci)
            board.push(move)
            post_id = position_store.get_or_create(board)
            post_eval_cp = cache_map.get(post_id, {}).get("eval_cp")

            mover_is_white = (ply_index % 2) == 1
            mover_is_self = (player_color == "white" and mover_is_white) or (
                player_color == "black" and not mover_is_white
            )

            your_cpl = None
            rep_cpl = None
            if mover_is_self:
                pre_eval_pov = _pov_eval(pre_eval_cp, player_color)
                post_eval_pov = _pov_eval(post_eval_cp, player_color)
                if pre_eval_pov is not None and post_eval_pov is not None:
                    your_cpl = max(0, pre_eval_pov - post_eval_pov)

                if (
                    allow_rep_cpl
                    and ply_index == game_deviation_ply_int
                    and ply_index - 1 < len(line_moves)
                ):
                    rep_move_uci = line_moves[ply_index - 1]
                    rep_move = chess.Move.from_uci(rep_move_uci)
                    if rep_move in pre_board.legal_moves:
                        rep_board = pre_board.copy(stack=False)
                        rep_board.push(rep_move)
                        rep_pos_id = position_store.get_or_create(rep_board)
                        rep_eval_cp = cache_map.get(rep_pos_id, {}).get("eval_cp")
                        rep_eval_pov = _pov_eval(rep_eval_cp, player_color)
                        if rep_eval_pov is not None and post_eval_pov is not None:
                            rep_cpl = max(0, rep_eval_pov - post_eval_pov)

            quality_label = _classify_quality(your_cpl)
            rows.append(
                (
                    game_id,
                    ply_index,
                    pos_id,
                    pre_eval_cp,
                    post_eval_cp,
                    best_uci,
                    your_cpl,
                    rep_cpl,
                    quality_label,
                )
            )

    conn.executemany(
        """
        INSERT OR REPLACE INTO analysis_ply (
            game_id, ply, pos_id, pre_eval_cp, post_eval_cp, best_uci,
            your_cpl, rep_cpl, quality_label
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def _normalize_rep_cpl_policy(
    conn,
    game_ids: list[int] | None = None,
) -> None:
    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"AND ap.game_id IN ({placeholders})"
        params = list(game_ids)
    conn.execute(
        f"""
        UPDATE analysis_ply AS ap
        SET rep_cpl = NULL
        WHERE rep_cpl IS NOT NULL
          {clause}
          AND NOT EXISTS (
            SELECT 1
            FROM matches m
            WHERE m.game_id = ap.game_id
              AND m.compliance = 'YOU_DEVIATED'
              AND m.deviation_ply_you IS NOT NULL
              AND ap.ply = m.deviation_ply_you
          )
        """,
        params,
    )
    conn.commit()


def _compute_time_patterns(
    conn,
    game_ids: list[int] | None = None,
) -> dict[int, int | None]:
    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"WHERE gp.game_id IN ({placeholders})"
        params = list(game_ids)

    rows = conn.execute(
        f"""
        SELECT gp.game_id, gp.ply, gp.time_spent_fraction, gp.is_self,
               gp.repertoire_class, g.is_daily
        FROM game_positions gp
        JOIN games g ON gp.game_id = g.id
        {clause}
        ORDER BY gp.game_id, gp.ply
        """,
        params,
    ).fetchall()

    patterns: dict[int, dict] = {}
    for row in rows:
        game_id = int(row["game_id"])
        entry = patterns.setdefault(
            game_id,
            {
                "first_out_ply": None,
                "in_book_frac_total": 0.0,
                "in_book_frac_count": 0,
                "is_daily": bool(row["is_daily"]),
            },
        )

        rep_class = row["repertoire_class"] or ""
        if entry["first_out_ply"] is None and rep_class == "OUT_OF_REPERTOIRE":
            entry["first_out_ply"] = int(row["ply"])

        if entry["is_daily"]:
            continue
        if not row["is_self"]:
            continue

        fraction = row["time_spent_fraction"]
        if fraction is None:
            continue

        if rep_class in {"IN_REPERTOIRE_MAIN", "IN_REPERTOIRE_OTHER"}:
            entry["in_book_frac_total"] += float(fraction)
            entry["in_book_frac_count"] += 1

    rows_to_insert = []
    first_out_map: dict[int, int | None] = {}
    for game_id, entry in patterns.items():
        avg_in_book = None
        if entry["in_book_frac_count"]:
            avg_in_book = entry["in_book_frac_total"] / entry["in_book_frac_count"]
        slow_in_book = 1 if avg_in_book is not None and avg_in_book >= SLOW_IN_BOOK_PCT else 0

        first_out_ply = entry["first_out_ply"]
        instant_out = (
            1
            if first_out_ply is not None and first_out_ply <= INSTANT_OUT_OF_BOOK_MAX_PLY
            else 0
        )

        rows_to_insert.append((game_id, slow_in_book, instant_out, 0))
        first_out_map[game_id] = first_out_ply

    if rows_to_insert:
        conn.executemany(
            """
            INSERT OR REPLACE INTO time_patterns (
                game_id, slow_in_book, instant_out_of_book, blunder_cluster
            )
            VALUES (?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()

    return first_out_map


def _update_blunder_clusters(
    conn,
    first_out_map: dict[int, int | None],
    game_ids: list[int] | None = None,
) -> None:
    if not first_out_map:
        return

    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"WHERE ap.game_id IN ({placeholders})"
        params = list(game_ids)

    rows = conn.execute(
        f"""
        SELECT ap.game_id, ap.ply, ap.your_cpl, gp.is_self
        FROM analysis_ply ap
        JOIN game_positions gp
          ON ap.game_id = gp.game_id AND ap.ply = gp.ply
        {clause}
        """,
        params,
    ).fetchall()

    flagged: set[int] = set()
    for row in rows:
        game_id = int(row["game_id"])
        first_out_ply = first_out_map.get(game_id)
        if first_out_ply is None:
            continue
        if not row["is_self"]:
            continue
        if row["your_cpl"] is None or row["your_cpl"] < BLUNDER_MIN:
            continue
        ply = int(row["ply"])
        if first_out_ply <= ply <= first_out_ply + BLUNDER_CLUSTER_WINDOW:
            flagged.add(game_id)

    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        conn.execute(
            f"UPDATE time_patterns SET blunder_cluster = 0 WHERE game_id IN ({placeholders})",
            tuple(game_ids),
        )
    else:
        conn.execute("UPDATE time_patterns SET blunder_cluster = 0")

    if flagged:
        placeholders = ",".join("?" for _ in flagged)
        conn.execute(
            f"""
            UPDATE time_patterns
            SET blunder_cluster = 1
            WHERE game_id IN ({placeholders})
            """,
            tuple(flagged),
        )
    conn.commit()


def _apply_novelty_tags(conn) -> None:
    rows = conn.execute(
        """
        SELECT g.id AS game_id, g.date, gp.ply, gp.pos_id, gp.uci_move
        FROM games g
        JOIN game_positions gp ON g.id = gp.game_id
        WHERE gp.repertoire_class = 'OUT_OF_REPERTOIRE'
        ORDER BY g.date, g.id, gp.ply
        """
    ).fetchall()

    seen_game: set[int] = set()
    seen_moves: set[tuple[int, str]] = set()
    novelty_games: set[int] = set()
    for row in rows:
        game_id = int(row["game_id"])
        if game_id in seen_game:
            continue
        seen_game.add(game_id)
        key = (int(row["pos_id"]), row["uci_move"])
        if key not in seen_moves:
            novelty_games.add(game_id)
            seen_moves.add(key)

    matches = conn.execute(
        "SELECT game_id, tags_json FROM matches"
    ).fetchall()
    updates = []
    for row in matches:
        game_id = int(row["game_id"])
        tags = []
        if row["tags_json"]:
            try:
                tags = json.loads(row["tags_json"])
            except json.JSONDecodeError:
                tags = []
        tags = [tag for tag in tags if tag != "NOVELTY"]
        if game_id in novelty_games:
            tags.append("NOVELTY")
        updates.append((json.dumps(tags), game_id))

    conn.executemany(
        "UPDATE matches SET tags_json = ? WHERE game_id = ?",
        updates,
    )
    conn.commit()


def _append_blunder_like_tags(conn, game_ids: list[int] | None = None) -> None:
    params = []
    clause = ""
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        clause = f"WHERE m.game_id IN ({placeholders})"
        params = list(game_ids)

    rows = conn.execute(
        f"""
        SELECT m.game_id, m.tags_json, m.deviation_ply_you, ap.your_cpl
        FROM matches m
        LEFT JOIN analysis_ply ap
          ON m.game_id = ap.game_id AND m.deviation_ply_you = ap.ply
        {clause}
        """,
        params,
    ).fetchall()

    updates = []
    for row in rows:
        tags = []
        if row["tags_json"]:
            try:
                tags = json.loads(row["tags_json"])
            except json.JSONDecodeError:
                tags = []
        if row["your_cpl"] is not None and row["your_cpl"] >= BLUNDER_MIN:
            if "BLUNDER_LIKE" not in tags:
                tags.append("BLUNDER_LIKE")
        updates.append((json.dumps(tags), int(row["game_id"])))

    conn.executemany(
        "UPDATE matches SET tags_json = ? WHERE game_id = ?",
        updates,
    )
    conn.commit()


def _load_engine_cache_map(
    conn,
    depth: int,
    engine_id: str | None = None,
) -> dict[int, dict]:
    if engine_id:
        rows = conn.execute(
            """
            SELECT pos_id, best_uci, eval_cp, wdl_json, analyzed_at
            FROM engine_cache
            WHERE depth = ? AND engine_id = ?
            ORDER BY analyzed_at DESC
            """,
            (depth, engine_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT pos_id, best_uci, eval_cp, wdl_json, analyzed_at
            FROM engine_cache
            WHERE depth = ?
            ORDER BY analyzed_at DESC
            """,
            (depth,),
        ).fetchall()
    cache_map: dict[int, dict] = {}
    for row in rows:
        pos_id = int(row["pos_id"])
        if pos_id in cache_map:
            continue
        cache_map[pos_id] = {
            "best_uci": row["best_uci"],
            "eval_cp": row["eval_cp"],
            "wdl_json": row["wdl_json"],
        }
    return cache_map


def _ensure_compliance_engine_state(conn, config, state: dict) -> dict:
    if state.get("engine") is not None:
        return state
    if not config.stockfish_path:
        raise RuntimeError(
            "Stockfish path is required for opponent deviation eval classification."
        )
    engine = chess.engine.SimpleEngine.popen_uci(config.stockfish_path)
    options = {}
    if config.engine_threads and config.engine_threads > 0:
        options["Threads"] = config.engine_threads
    if config.engine_hash_mb and config.engine_hash_mb > 0:
        options["Hash"] = config.engine_hash_mb
    if options:
        try:
            engine.configure(options)
        except Exception:
            pass
    base_engine_id = engine_identity(engine, config.stockfish_path)
    engine_id = _effective_engine_id(base_engine_id, config)
    cache_map = _load_engine_cache_map(conn, config.engine_depth, engine_id=engine_id)
    state["engine"] = engine
    state["engine_id"] = engine_id
    state["cache_map"] = cache_map
    state["pending_rows"] = []
    return state


def _flush_compliance_cache_rows(conn, state: dict) -> None:
    rows = state.get("pending_rows") or []
    if not rows:
        return
    conn.executemany(
        """
        INSERT OR REPLACE INTO engine_cache (
            pos_id, depth, engine_id, best_uci, eval_cp, wdl_json, analyzed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    state["pending_rows"] = []


def _close_compliance_engine_state(conn, state: dict) -> None:
    try:
        _flush_compliance_cache_rows(conn, state)
    finally:
        engine = state.get("engine")
        if engine is not None:
            try:
                engine.quit()
            except Exception:
                pass
        state["engine"] = None


def _board_before_ply(game_moves_uci: list[str], ply: int) -> chess.Board | None:
    if ply <= 0 or ply > len(game_moves_uci):
        return None
    board = chess.Board()
    for move_uci in game_moves_uci[: ply - 1]:
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            return None
        board.push(move)
    return board


def _evaluate_pos_id_on_demand(
    conn,
    config,
    state: dict,
    pos_id: int,
    board: chess.Board,
) -> int | None:
    state = _ensure_compliance_engine_state(conn, config, state)
    cache_map = state["cache_map"]
    eval_cp = cache_map.get(pos_id, {}).get("eval_cp")
    if eval_cp is not None:
        return eval_cp

    engine = state["engine"]
    best_uci, eval_cp, wdl = analyze_position(
        engine,
        board,
        config.engine_depth,
        mode=config.engine_mode,
        max_time_ms=config.engine_max_time_ms,
    )
    wdl_json = json.dumps(wdl) if wdl is not None else None
    cache_map[pos_id] = {
        "best_uci": best_uci,
        "eval_cp": eval_cp,
        "wdl_json": wdl_json,
    }
    if config.enable_engine_cache:
        state["pending_rows"].append(
            (
                pos_id,
                config.engine_depth,
                state["engine_id"],
                best_uci,
                eval_cp,
                wdl_json,
                datetime.now(timezone.utc).isoformat(),
            )
        )
    return eval_cp


def _opponent_deviation_eval_delta_cp(
    conn,
    config,
    position_store: PositionStore,
    game: dict,
    opponent_deviation_ply: int | None,
    state: dict,
) -> int | None:
    ply = int(opponent_deviation_ply or 0)
    if ply <= 0:
        return None

    row = conn.execute(
        """
        SELECT pre_eval_cp, post_eval_cp
        FROM analysis_ply
        WHERE game_id = ? AND ply = ?
        """,
        (game["game_id"], ply),
    ).fetchone()
    pre_eval_cp = row["pre_eval_cp"] if row else None
    post_eval_cp = row["post_eval_cp"] if row else None
    if pre_eval_cp is not None and post_eval_cp is not None:
        return int(post_eval_cp) - int(pre_eval_cp)

    moves_uci = game.get("moves_uci") or []
    if ply > len(moves_uci):
        return None

    pos_ids = game.get("pos_ids") or []
    pre_pos_id = int(pos_ids[ply - 1]) if ply - 1 < len(pos_ids) else None
    post_pos_id = int(pos_ids[ply]) if ply < len(pos_ids) else None

    board_before = _board_before_ply(moves_uci, ply)
    if board_before is None:
        return None
    move = chess.Move.from_uci(moves_uci[ply - 1])
    if move not in board_before.legal_moves:
        return None
    board_after = board_before.copy(stack=False)
    board_after.push(move)

    if pre_pos_id is None:
        pre_pos_id = position_store.get_or_create(board_before)
    if post_pos_id is None:
        post_pos_id = position_store.get_or_create(board_after)

    if pre_eval_cp is None:
        pre_eval_cp = _evaluate_pos_id_on_demand(
            conn, config, state, pre_pos_id, board_before
        )
    if post_eval_cp is None:
        post_eval_cp = _evaluate_pos_id_on_demand(
            conn, config, state, post_pos_id, board_after
        )
    if pre_eval_cp is None or post_eval_cp is None:
        return None
    return int(post_eval_cp) - int(pre_eval_cp)


def compute_deviation_rep_cpl(
    conn,
    config,
    game_id: int,
    ply: int,
) -> tuple[int | None, str | None]:
    target_ply = int(ply or 0)
    if target_ply <= 0:
        return None, "Invalid ply."

    match_row = conn.execute(
        """
        SELECT compliance, deviation_ply_you
        FROM matches
        WHERE game_id = ?
        """,
        (int(game_id),),
    ).fetchone()
    if not match_row:
        return None, "Match row not found."

    compliance_value = str(match_row["compliance"] or "")
    deviation_ply = int(match_row["deviation_ply_you"] or 0)
    if compliance_value != "YOU_DEVIATED":
        return None, "Rep CPL is available only for YOU_DEVIATED games."
    if deviation_ply <= 0 or target_ply != deviation_ply:
        return None, "Rep CPL is available only at the self-deviation ply."

    contexts = _load_game_contexts(conn, [int(game_id)])
    if not contexts:
        return None, "Game context not found."
    game = contexts[0]

    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    _attach_effective_matched_lines(
        conn,
        [game],
        line_data,
        config.matching_mode,
        runtime_line_ids=None,
    )
    line_id = game.get("matched_line_id")
    if not line_id:
        return None, "Could not resolve repertoire line for this game."

    line_moves = lines_by_id.get(line_id or "", [])
    if target_ply - 1 >= len(line_moves):
        return None, "Repertoire line does not include this deviation ply."

    moves_uci = game.get("moves_uci") or []
    if target_ply > len(moves_uci):
        return None, "Game move list is shorter than the requested ply."

    board_before = _board_before_ply(moves_uci, target_ply)
    if board_before is None:
        return None, "Unable to reconstruct board at deviation ply."

    played_move = chess.Move.from_uci(moves_uci[target_ply - 1])
    if played_move not in board_before.legal_moves:
        return None, "Played move is not legal in reconstructed position."
    board_after = board_before.copy(stack=False)
    board_after.push(played_move)

    rep_move = chess.Move.from_uci(line_moves[target_ply - 1])
    if rep_move not in board_before.legal_moves:
        return None, "Expected repertoire move is not legal at deviation ply."
    rep_board = board_before.copy(stack=False)
    rep_board.push(rep_move)

    position_store = PositionStore(conn)
    pos_ids = game.get("pos_ids") or []
    pre_pos_id = int(pos_ids[target_ply - 1]) if target_ply - 1 < len(pos_ids) else position_store.get_or_create(board_before)
    post_pos_id = int(pos_ids[target_ply]) if target_ply < len(pos_ids) else position_store.get_or_create(board_after)
    rep_pos_id = position_store.get_or_create(rep_board)

    row = conn.execute(
        """
        SELECT pos_id, pre_eval_cp, post_eval_cp, best_uci, your_cpl, quality_label
        FROM analysis_ply
        WHERE game_id = ? AND ply = ?
        """,
        (int(game_id), target_ply),
    ).fetchone()

    stored_pos_id = int(row["pos_id"]) if row and row["pos_id"] is not None else pre_pos_id
    pre_eval_cp = row["pre_eval_cp"] if row else None
    post_eval_cp = row["post_eval_cp"] if row else None
    best_uci = row["best_uci"] if row else None
    your_cpl = row["your_cpl"] if row else None
    quality_label = row["quality_label"] if row else None

    state: dict = {"engine": None}
    try:
        if pre_eval_cp is None:
            pre_eval_cp = _evaluate_pos_id_on_demand(
                conn, config, state, pre_pos_id, board_before
            )
        if post_eval_cp is None:
            post_eval_cp = _evaluate_pos_id_on_demand(
                conn, config, state, post_pos_id, board_after
            )
        rep_eval_cp = _evaluate_pos_id_on_demand(
            conn, config, state, rep_pos_id, rep_board
        )

        cached_pre = state.get("cache_map", {}).get(pre_pos_id, {})
        if not best_uci:
            best_uci = cached_pre.get("best_uci")

        player_color = game.get("player_color") or "white"
        pre_eval_pov = _pov_eval(pre_eval_cp, player_color)
        post_eval_pov = _pov_eval(post_eval_cp, player_color)
        rep_eval_pov = _pov_eval(rep_eval_cp, player_color)

        rep_cpl = None
        if rep_eval_pov is not None and post_eval_pov is not None:
            rep_cpl = max(0, rep_eval_pov - post_eval_pov)
        if your_cpl is None and pre_eval_pov is not None and post_eval_pov is not None:
            your_cpl = max(0, pre_eval_pov - post_eval_pov)
        if not quality_label:
            quality_label = _classify_quality(your_cpl)

        conn.execute(
            """
            INSERT OR REPLACE INTO analysis_ply (
                game_id, ply, pos_id, pre_eval_cp, post_eval_cp, best_uci,
                your_cpl, rep_cpl, quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(game_id),
                target_ply,
                stored_pos_id,
                pre_eval_cp,
                post_eval_cp,
                best_uci,
                your_cpl,
                rep_cpl,
                quality_label,
            ),
        )
        conn.commit()
        _normalize_rep_cpl_policy(conn, [int(game_id)])
        return rep_cpl, None
    finally:
        _close_compliance_engine_state(conn, state)

def run_analysis(
    conn,
    config,
    reset_db: bool,
    progress_cb: Callable[[dict], None] | None = None,
) -> None:
    _emit_progress(progress_cb, "Preparing analysis", done=0, total=0)
    if reset_db:
        _clear_data(conn)

    repertoire_root = Path(config.repertoire_dir)
    games_root = Path(config.games_dir)

    rep_files = _list_pgn_files(repertoire_root)
    game_files = _list_pgn_files(games_root)

    if not config.incremental_analysis:
        _clear_data(conn)

    existing_rep = _load_source_files(conn, "repertoire")
    existing_games = _load_source_files(conn, "games")

    rep_hashes = {str(path): _compute_file_hash(path) for path in rep_files}
    game_hashes = {str(path): _compute_file_hash(path) for path in game_files}

    if config.incremental_analysis:
        changed_rep = [
            path for path in rep_files if existing_rep.get(str(path)) != rep_hashes[str(path)]
        ]
        removed_rep = [path for path in existing_rep if path not in rep_hashes]
        changed_games = [
            path
            for path in game_files
            if existing_games.get(str(path)) != game_hashes[str(path)]
        ]
        removed_games = [path for path in existing_games if path not in game_hashes]
    else:
        changed_rep = rep_files
        removed_rep = list(existing_rep)
        changed_games = game_files
        removed_games = list(existing_games)

    if removed_rep:
        placeholders = ",".join("?" for _ in removed_rep)
        conn.execute(
            f"DELETE FROM repertoire_lines WHERE source_pgn IN ({placeholders})",
            tuple(removed_rep),
        )
        conn.commit()

    if changed_rep:
        placeholders = ",".join("?" for _ in changed_rep)
        conn.execute(
            f"DELETE FROM repertoire_lines WHERE source_pgn IN ({placeholders})",
            tuple(str(p) for p in changed_rep),
        )
        conn.commit()

    position_store = PositionStore(conn)
    if changed_rep:
        lines = repertoire_loader.load_repertoire_lines(
            str(repertoire_root), changed_rep, config.player_names
        )
        _insert_repertoire_lines(conn, position_store, lines)

    _update_source_files(conn, "repertoire", rep_hashes)

    repertoire_changed = bool(changed_rep or removed_rep)
    if repertoire_changed or not config.incremental_analysis:
        _build_repertoire_edges(conn)
        _ensure_trainer_state(conn)

    if removed_games:
        placeholders = ",".join("?" for _ in removed_games)
        conn.execute(
            f"DELETE FROM games WHERE source_pgn IN ({placeholders})",
            tuple(removed_games),
        )
        conn.commit()

    contexts: list[dict] = []
    if changed_games:
        games = game_loader.load_games_from_dir(
            str(games_root), config.player_names, changed_games
        )
        contexts = _insert_games(conn, position_store, games)

    _update_source_files(conn, "games", game_hashes)

    if repertoire_changed or not config.incremental_analysis:
        games_to_match = _load_game_contexts(conn)
    else:
        games_to_match = contexts

    if not games_to_match:
        if repertoire_changed or removed_games:
            propositions.rebuild_missing_coverage_propositions(
                conn,
                threshold=config.missing_coverage_proposal_threshold,
            )
        _emit_progress(progress_cb, "Analysis complete", done=1, total=1)
        return

    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    line_pos_by_id = {line["line_id"]: line["pos_ids"] for line in line_data}
    edge_map = _load_edge_map(conn)
    repertoire_positions = _load_repertoire_positions(conn)

    games_to_match.sort(key=lambda g: g.get("date") or "")

    match_rows = []
    runtime_line_ids: dict[int, str | None] = {}
    compliance_engine_state: dict = {"engine": None}
    try:
        for game in games_to_match:
            match_result = matching.find_best_match(
                game["moves_uci"],
                game["pos_ids"],
                line_data,
                game["player_color"],
                config.matching_mode,
            )

            line_moves = lines_by_id.get(match_result.matched_line_id or "", [])
            line_pos_ids = line_pos_by_id.get(match_result.matched_line_id or "", [])
            classification_result, _ = _update_game_classification(
                conn,
                game,
                line_moves,
                line_pos_ids,
                edge_map,
                repertoire_positions,
            )

            opp_delta_cp = None
            if (
                match_result.deviation_ply_opp is not None
                and (
                    match_result.deviation_ply_self is None
                    or match_result.deviation_ply_opp < match_result.deviation_ply_self
                )
            ):
                opp_delta_cp = _opponent_deviation_eval_delta_cp(
                    conn,
                    config,
                    position_store,
                    game,
                    match_result.deviation_ply_opp,
                    compliance_engine_state,
                )
            compliance_label = compliance.classify_compliance_with_completion_and_eval(
                match_result.deviation_ply_opp,
                match_result.deviation_ply_self,
                match_result.max_matched_ply,
                len(line_moves),
                opp_delta_cp,
            )
            who_left = compliance.who_left_first(
                match_result.deviation_ply_opp, match_result.deviation_ply_self
            )
            stored_line_id = (
                match_result.matched_line_id
                if compliance_label == "FULLY_COMPLIANT"
                else None
            )

            tags = []
            if config.matching_mode == "STRICT" and match_result.deviation_ply_self:
                idx = match_result.deviation_ply_self - 1
                if idx < len(game["pos_ids"]):
                    pos_id = game["pos_ids"][idx]
                    if pos_id in repertoire_positions:
                        tags.append("TRANSPOSITION")

            match_rows.append(
                (
                    game["game_id"],
                    stored_line_id,
                    config.matching_mode,
                    match_result.max_matched_ply,
                    match_result.deviation_ply_self,
                    match_result.deviation_ply_opp,
                    compliance_label,
                    who_left,
                    1 if classification_result["recovered_to_rep"] else 0,
                    1 if classification_result["opponent_dev_to_known"] else 0,
                    json.dumps(tags),
                    None,
                )
            )
            runtime_line_ids[int(game["game_id"])] = match_result.matched_line_id
    finally:
        _close_compliance_engine_state(conn, compliance_engine_state)

    conn.executemany(
        """
        INSERT OR REPLACE INTO matches (
            game_id, matched_line_id, matching_mode, max_matched_ply,
            deviation_ply_you, deviation_ply_opp, compliance, who_left_first,
            recovered_to_rep, opponent_dev_to_known, tags_json, tie_lines_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        match_rows,
    )
    conn.commit()
    _enforce_match_storage_policy(conn)
    propositions.rebuild_missing_coverage_propositions(
        conn,
        threshold=config.missing_coverage_proposal_threshold,
    )

    _apply_novelty_tags(conn)
    _apply_game_based_trainer_priority(conn, runtime_line_ids=runtime_line_ids)

    game_ids = [game["game_id"] for game in games_to_match]
    first_out_map = _compute_time_patterns(conn, game_ids)

    if not config.stockfish_path:
        raise RuntimeError("Stockfish path is required for engine analysis.")

    games_for_engine = games_to_match
    if repertoire_changed and config.incremental_analysis:
        games_for_engine = _load_game_contexts(conn)

    _emit_progress(
        progress_cb,
        "Preparing engine",
        done=0,
        total=len(games_for_engine),
        depth=config.engine_depth,
        mode=config.engine_mode,
        max_time_ms=config.engine_max_time_ms,
    )
    with chess.engine.SimpleEngine.popen_uci(config.stockfish_path) as engine:
        options = {}
        if config.engine_threads and config.engine_threads > 0:
            options["Threads"] = config.engine_threads
        if config.engine_hash_mb and config.engine_hash_mb > 0:
            options["Hash"] = config.engine_hash_mb
        if options:
            try:
                engine.configure(options)
            except Exception:
                pass
        base_engine_id = engine_identity(engine, config.stockfish_path)
        engine_id = _effective_engine_id(base_engine_id, config)
        cache_map = _build_engine_cache(
            conn,
            engine,
            position_store,
            games_for_engine,
            config.engine_depth,
            engine_id,
            config.enable_engine_cache,
            config,
            progress_cb=progress_cb,
        )

    _attach_effective_matched_lines(
        conn,
        games_for_engine,
        line_data,
        config.matching_mode,
        runtime_line_ids=runtime_line_ids,
    )

    _emit_progress(
        progress_cb,
        "Rebuilding analysis_ply",
        done=0,
        total=len(games_for_engine),
    )
    _compute_analysis_ply(
        conn,
        position_store,
        games_for_engine,
        cache_map,
        lines_by_id,
    )
    _normalize_rep_cpl_policy(
        conn,
        [int(game["game_id"]) for game in games_for_engine],
    )

    _emit_progress(
        progress_cb,
        "Refreshing review/insights",
        done=0,
        total=len(game_ids),
    )
    _update_blunder_clusters(conn, first_out_map, game_ids)
    _append_blunder_like_tags(conn, game_ids)

    review_items = review.generate_review_items(conn, config.review_top_n)
    review.store_review_items(conn, review_items)
    insights = insights_module.generate_insights(
        conn, config.review_top_n, config.tabiya_top_n
    )
    insights_module.store_insights(conn, insights)
    _emit_progress(progress_cb, "Analysis complete", done=1, total=1)


def run_engine_analysis_only(
    conn,
    config,
    progress_cb: Callable[[dict], None] | None = None,
) -> None:
    _emit_progress(progress_cb, "Preparing engine", done=0, total=0)
    if not config.stockfish_path:
        raise RuntimeError("Stockfish path is required for engine analysis.")

    games_for_engine = _load_game_contexts(conn)
    if not games_for_engine:
        _emit_progress(progress_cb, "No games to analyze", done=0, total=0)
        return

    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    position_store = PositionStore(conn)

    with chess.engine.SimpleEngine.popen_uci(config.stockfish_path) as engine:
        options = {}
        if config.engine_threads and config.engine_threads > 0:
            options["Threads"] = config.engine_threads
        if config.engine_hash_mb and config.engine_hash_mb > 0:
            options["Hash"] = config.engine_hash_mb
        if options:
            try:
                engine.configure(options)
            except Exception:
                pass
        base_engine_id = engine_identity(engine, config.stockfish_path)
        engine_id = _effective_engine_id(base_engine_id, config)
        cache_map = _build_engine_cache(
            conn,
            engine,
            position_store,
            games_for_engine,
            config.engine_depth,
            engine_id,
            config.enable_engine_cache,
            config,
            progress_cb=progress_cb,
        )

    _attach_effective_matched_lines(
        conn,
        games_for_engine,
        line_data,
        config.matching_mode,
        runtime_line_ids=None,
    )

    _emit_progress(
        progress_cb,
        "Rebuilding analysis_ply",
        done=0,
        total=len(games_for_engine),
    )
    conn.execute("DELETE FROM analysis_ply")
    conn.commit()
    _compute_analysis_ply(
        conn,
        position_store,
        games_for_engine,
        cache_map,
        lines_by_id,
    )
    _normalize_rep_cpl_policy(
        conn,
        [int(game["game_id"]) for game in games_for_engine],
    )

    game_ids = [game["game_id"] for game in games_for_engine]
    _emit_progress(
        progress_cb,
        "Refreshing review/insights",
        done=0,
        total=len(game_ids),
    )
    first_out_map = _compute_time_patterns(conn, game_ids)
    _update_blunder_clusters(conn, first_out_map, game_ids)
    _apply_novelty_tags(conn)
    _append_blunder_like_tags(conn, game_ids)
    review_items = review.generate_review_items(conn, config.review_top_n)
    review.store_review_items(conn, review_items)
    insights = insights_module.generate_insights(
        conn, config.review_top_n, config.tabiya_top_n
    )
    insights_module.store_insights(conn, insights)
    _emit_progress(progress_cb, "Engine analysis complete", done=1, total=1)


def run_line_matching_reanalysis(
    conn,
    config,
    progress_cb: Callable[[dict], None] | None = None,
) -> None:
    games_to_match = _load_game_contexts(conn)
    if not games_to_match:
        _emit_progress(progress_cb, "No games to rematch", done=0, total=0)
        return

    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    line_pos_by_id = {line["line_id"]: line["pos_ids"] for line in line_data}
    edge_map = _load_edge_map(conn)
    repertoire_positions = _load_repertoire_positions(conn)
    position_store = PositionStore(conn)

    games_to_match.sort(key=lambda g: g.get("date") or "")
    _emit_progress(
        progress_cb,
        "Reanalyzing matches",
        done=0,
        total=len(games_to_match),
    )

    match_rows = []
    runtime_line_ids: dict[int, str | None] = {}
    compliance_engine_state: dict = {"engine": None}
    try:
        for index, game in enumerate(games_to_match, start=1):
            match_result = matching.find_best_match(
                game["moves_uci"],
                game["pos_ids"],
                line_data,
                game["player_color"],
                config.matching_mode,
            )

            line_moves = lines_by_id.get(match_result.matched_line_id or "", [])
            line_pos_ids = line_pos_by_id.get(match_result.matched_line_id or "", [])
            classification_result, _ = _update_game_classification(
                conn,
                game,
                line_moves,
                line_pos_ids,
                edge_map,
                repertoire_positions,
            )

            opp_delta_cp = None
            if (
                match_result.deviation_ply_opp is not None
                and (
                    match_result.deviation_ply_self is None
                    or match_result.deviation_ply_opp < match_result.deviation_ply_self
                )
            ):
                opp_delta_cp = _opponent_deviation_eval_delta_cp(
                    conn,
                    config,
                    position_store,
                    game,
                    match_result.deviation_ply_opp,
                    compliance_engine_state,
                )
            compliance_label = compliance.classify_compliance_with_completion_and_eval(
                match_result.deviation_ply_opp,
                match_result.deviation_ply_self,
                match_result.max_matched_ply,
                len(line_moves),
                opp_delta_cp,
            )
            who_left = compliance.who_left_first(
                match_result.deviation_ply_opp, match_result.deviation_ply_self
            )
            stored_line_id = (
                match_result.matched_line_id
                if compliance_label == "FULLY_COMPLIANT"
                else None
            )

            tags = []
            if config.matching_mode == "STRICT" and match_result.deviation_ply_self:
                idx = match_result.deviation_ply_self - 1
                if idx < len(game["pos_ids"]):
                    pos_id = game["pos_ids"][idx]
                    if pos_id in repertoire_positions:
                        tags.append("TRANSPOSITION")

            match_rows.append(
                (
                    game["game_id"],
                    stored_line_id,
                    config.matching_mode,
                    match_result.max_matched_ply,
                    match_result.deviation_ply_self,
                    match_result.deviation_ply_opp,
                    compliance_label,
                    who_left,
                    1 if classification_result["recovered_to_rep"] else 0,
                    1 if classification_result["opponent_dev_to_known"] else 0,
                    json.dumps(tags),
                    None,
                )
            )
            runtime_line_ids[int(game["game_id"])] = match_result.matched_line_id
            if (
                index == len(games_to_match)
                or index % 50 == 0
            ):
                _emit_progress(
                    progress_cb,
                    "Reanalyzing matches",
                    done=index,
                    total=len(games_to_match),
                )
    finally:
        _close_compliance_engine_state(conn, compliance_engine_state)

    conn.executemany(
        """
        INSERT OR REPLACE INTO matches (
            game_id, matched_line_id, matching_mode, max_matched_ply,
            deviation_ply_you, deviation_ply_opp, compliance, who_left_first,
            recovered_to_rep, opponent_dev_to_known, tags_json, tie_lines_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        match_rows,
    )
    conn.commit()
    _enforce_match_storage_policy(conn)
    propositions.rebuild_missing_coverage_propositions(
        conn,
        threshold=config.missing_coverage_proposal_threshold,
    )
    _apply_novelty_tags(conn)

    _emit_progress(
        progress_cb,
        "Refreshing trainer priority",
        done=0,
        total=len(games_to_match),
    )
    _apply_game_based_trainer_priority(conn, runtime_line_ids=runtime_line_ids)

    game_ids = [game["game_id"] for game in games_to_match]
    _emit_progress(
        progress_cb,
        "Refreshing review/insights",
        done=0,
        total=len(game_ids),
    )
    first_out_map = _compute_time_patterns(conn, game_ids)
    _update_blunder_clusters(conn, first_out_map, game_ids)
    _append_blunder_like_tags(conn, game_ids)

    review_items = review.generate_review_items(conn, config.review_top_n)
    review.store_review_items(conn, review_items)
    insights = insights_module.generate_insights(
        conn, config.review_top_n, config.tabiya_top_n
    )
    insights_module.store_insights(conn, insights)
    _emit_progress(progress_cb, "Line matching reanalysis complete", done=1, total=1)


def run_game_details_reanalysis(
    conn,
    config,
    progress_cb: Callable[[dict], None] | None = None,
) -> None:
    _emit_progress(progress_cb, "Preparing engine", done=0, total=0)
    if not config.stockfish_path:
        raise RuntimeError("Stockfish path is required for engine analysis.")

    games_for_engine = _load_game_contexts(conn)
    if not games_for_engine:
        _emit_progress(progress_cb, "No games to analyze", done=0, total=0)
        return

    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    position_store = PositionStore(conn)

    with chess.engine.SimpleEngine.popen_uci(config.stockfish_path) as engine:
        options = {}
        if config.engine_threads and config.engine_threads > 0:
            options["Threads"] = config.engine_threads
        if config.engine_hash_mb and config.engine_hash_mb > 0:
            options["Hash"] = config.engine_hash_mb
        if options:
            try:
                engine.configure(options)
            except Exception:
                pass
        base_engine_id = engine_identity(engine, config.stockfish_path)
        engine_id = _effective_engine_id(base_engine_id, config)
        cache_map = _build_engine_cache(
            conn,
            engine,
            position_store,
            games_for_engine,
            config.engine_depth,
            engine_id,
            config.enable_engine_cache,
            config,
            progress_cb=progress_cb,
        )

    _attach_effective_matched_lines(
        conn,
        games_for_engine,
        line_data,
        config.matching_mode,
        runtime_line_ids=None,
    )

    _emit_progress(
        progress_cb,
        "Rebuilding analysis_ply",
        done=0,
        total=len(games_for_engine),
    )
    conn.execute("DELETE FROM analysis_ply")
    conn.commit()
    _compute_analysis_ply(
        conn,
        position_store,
        games_for_engine,
        cache_map,
        lines_by_id,
    )
    _normalize_rep_cpl_policy(
        conn,
        [int(game["game_id"]) for game in games_for_engine],
    )

    game_ids = [game["game_id"] for game in games_for_engine]
    _emit_progress(
        progress_cb,
        "Refreshing review/insights",
        done=0,
        total=len(game_ids),
    )
    first_out_map = _compute_time_patterns(conn, game_ids)
    _update_blunder_clusters(conn, first_out_map, game_ids)
    _apply_novelty_tags(conn)
    _append_blunder_like_tags(conn, game_ids)

    review_items = review.generate_review_items(conn, config.review_top_n)
    review.store_review_items(conn, review_items)
    insights = insights_module.generate_insights(
        conn, config.review_top_n, config.tabiya_top_n
    )
    insights_module.store_insights(conn, insights)
    _emit_progress(progress_cb, "Game details reanalysis complete", done=1, total=1)


def reanalyze_game(conn, config, game_id: int) -> None:
    line_data = _load_line_data(conn)
    lines_by_id = {line["line_id"]: line["moves_uci"] for line in line_data}
    line_pos_by_id = {line["line_id"]: line["pos_ids"] for line in line_data}
    edge_map = _load_edge_map(conn)
    repertoire_positions = _load_repertoire_positions(conn)
    position_store = PositionStore(conn)

    game_contexts = _load_game_contexts(conn, [game_id])
    if not game_contexts:
        return

    game = game_contexts[0]
    match_result = matching.find_best_match(
        game["moves_uci"],
        game["pos_ids"],
        line_data,
        game["player_color"],
        config.matching_mode,
    )

    line_moves = lines_by_id.get(match_result.matched_line_id or "", [])
    line_pos_ids = line_pos_by_id.get(match_result.matched_line_id or "", [])
    classification_result, _ = _update_game_classification(
        conn,
        game,
        line_moves,
        line_pos_ids,
        edge_map,
        repertoire_positions,
    )

    compliance_engine_state: dict = {"engine": None}
    try:
        opp_delta_cp = None
        if (
            match_result.deviation_ply_opp is not None
            and (
                match_result.deviation_ply_self is None
                or match_result.deviation_ply_opp < match_result.deviation_ply_self
            )
        ):
            opp_delta_cp = _opponent_deviation_eval_delta_cp(
                conn,
                config,
                position_store,
                game,
                match_result.deviation_ply_opp,
                compliance_engine_state,
            )
        compliance_label = compliance.classify_compliance_with_completion_and_eval(
            match_result.deviation_ply_opp,
            match_result.deviation_ply_self,
            match_result.max_matched_ply,
            len(line_moves),
            opp_delta_cp,
        )
    finally:
        _close_compliance_engine_state(conn, compliance_engine_state)
    who_left = compliance.who_left_first(
        match_result.deviation_ply_opp, match_result.deviation_ply_self
    )
    stored_line_id = (
        match_result.matched_line_id
        if compliance_label == "FULLY_COMPLIANT"
        else None
    )

    tags = []
    if config.matching_mode == "STRICT" and match_result.deviation_ply_self:
        idx = match_result.deviation_ply_self - 1
        if idx < len(game["pos_ids"]):
            pos_id = game["pos_ids"][idx]
            if pos_id in repertoire_positions:
                tags.append("TRANSPOSITION")

    conn.execute(
        """
        INSERT OR REPLACE INTO matches (
            game_id, matched_line_id, matching_mode, max_matched_ply,
            deviation_ply_you, deviation_ply_opp, compliance, who_left_first,
            recovered_to_rep, opponent_dev_to_known, tags_json, tie_lines_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game["game_id"],
            stored_line_id,
            config.matching_mode,
            match_result.max_matched_ply,
            match_result.deviation_ply_self,
            match_result.deviation_ply_opp,
            compliance_label,
            who_left,
            1 if classification_result["recovered_to_rep"] else 0,
            1 if classification_result["opponent_dev_to_known"] else 0,
            json.dumps(tags),
            None,
        ),
    )
    conn.commit()
    _enforce_match_storage_policy(conn)
    propositions.rebuild_missing_coverage_propositions(
        conn,
        threshold=config.missing_coverage_proposal_threshold,
    )

    _apply_novelty_tags(conn)
    _apply_game_based_trainer_priority(
        conn,
        runtime_line_ids={int(game_id): match_result.matched_line_id},
    )
    first_out_map = _compute_time_patterns(conn, [game_id])

    active_engine_id: str | None = None
    if config.stockfish_path:
        try:
            with chess.engine.SimpleEngine.popen_uci(config.stockfish_path) as engine:
                options = {}
                if config.engine_threads and config.engine_threads > 0:
                    options["Threads"] = config.engine_threads
                if config.engine_hash_mb and config.engine_hash_mb > 0:
                    options["Hash"] = config.engine_hash_mb
                if options:
                    try:
                        engine.configure(options)
                    except Exception:
                        pass
                base_engine_id = engine_identity(engine, config.stockfish_path)
                active_engine_id = _effective_engine_id(base_engine_id, config)
        except Exception:
            active_engine_id = None
    cache_map = _load_engine_cache_map(
        conn,
        config.engine_depth,
        engine_id=active_engine_id,
    )
    if cache_map:
        position_store = PositionStore(conn)
        game["matched_line_id"] = match_result.matched_line_id
        _compute_analysis_ply(
            conn,
            position_store,
            [game],
            cache_map,
            lines_by_id,
        )
    _normalize_rep_cpl_policy(conn, [int(game_id)])

    _update_blunder_clusters(conn, first_out_map, [game_id])
    _append_blunder_like_tags(conn, [game_id])

    review_items = review.generate_review_items(conn, config.review_top_n)
    review.store_review_items(conn, review_items)
    insights = insights_module.generate_insights(
        conn, config.review_top_n, config.tabiya_top_n
    )
    insights_module.store_insights(conn, insights)


def sync_repertoire_only(conn, config) -> None:
    repertoire_root = Path(config.repertoire_dir)
    rep_files = _list_pgn_files(repertoire_root)
    rep_hashes = {str(path): _compute_file_hash(path) for path in rep_files}
    existing_rep = _load_source_files(conn, "repertoire")

    changed_rep = [
        path for path in rep_files if existing_rep.get(str(path)) != rep_hashes[str(path)]
    ]
    removed_rep = [path for path in existing_rep if path not in rep_hashes]

    if removed_rep:
        placeholders = ",".join("?" for _ in removed_rep)
        conn.execute(
            f"DELETE FROM repertoire_lines WHERE source_pgn IN ({placeholders})",
            tuple(removed_rep),
        )
        conn.commit()

    if changed_rep:
        placeholders = ",".join("?" for _ in changed_rep)
        conn.execute(
            f"DELETE FROM repertoire_lines WHERE source_pgn IN ({placeholders})",
            tuple(str(p) for p in changed_rep),
        )
        conn.commit()

    position_store = PositionStore(conn)
    if changed_rep:
        lines = repertoire_loader.load_repertoire_lines(
            str(repertoire_root), changed_rep, config.player_names
        )
        _insert_repertoire_lines(conn, position_store, lines)

    _update_source_files(conn, "repertoire", rep_hashes)

    if changed_rep or removed_rep or not existing_rep:
        _build_repertoire_edges(conn)
    _ensure_trainer_state(conn)


def discard_repertoire_line(conn, line_id: str, discard_path: Path) -> tuple[bool, str]:
    row = conn.execute(
        "SELECT source_pgn FROM repertoire_lines WHERE line_id = ?", (line_id,)
    ).fetchone()
    if not row or not row["source_pgn"]:
        return False, "Source PGN not found for this line."

    source_path = Path(row["source_pgn"])
    if not source_path.exists():
        return False, f"Source PGN missing: {source_path}"

    kept_games: list[chess.pgn.Game] = []
    discarded_games: list[chess.pgn.Game] = []
    with source_path.open("r", encoding="utf-8", errors="ignore") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            event_tag = (game.headers.get("Event") or "").strip()
            if event_tag == line_id:
                discarded_games.append(game)
            else:
                kept_games.append(game)

    if not discarded_games:
        return False, "Line not found in source PGN."

    with source_path.open("w", encoding="utf-8") as handle:
        first = True
        for game in kept_games:
            if not first:
                handle.write("\n\n")
            exporter = chess.pgn.FileExporter(handle)
            game.accept(exporter)
            first = False

    discard_path.parent.mkdir(parents=True, exist_ok=True)
    with discard_path.open("a", encoding="utf-8") as handle:
        if discard_path.exists() and discard_path.stat().st_size > 0:
            handle.write("\n\n")
        for idx, game in enumerate(discarded_games):
            if idx > 0:
                handle.write("\n\n")
            exporter = chess.pgn.FileExporter(handle)
            game.accept(exporter)

    conn.execute("DELETE FROM repertoire_lines WHERE line_id = ?", (line_id,))
    conn.commit()

    new_hash = _compute_file_hash(source_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO source_files (path, file_hash, file_type, last_seen)
        VALUES (?, ?, 'repertoire', ?)
        """,
        (str(source_path), new_hash, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    _build_repertoire_edges(conn)
    _ensure_trainer_state(conn)
    return True, "Discarded."
