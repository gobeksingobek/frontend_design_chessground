from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Iterable

import asyncpg

from backend import db
from backend.settings import SETTINGS


def _connect_sqlite(sqlite_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_jsonb(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return json.dumps(parsed)


def _iter_rows(conn: sqlite3.Connection, query: str, batch_size: int) -> Iterable[list[sqlite3.Row]]:
    cursor = conn.execute(query)
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            return
        yield rows


def _sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"] or 0)


async def _postgres_count(conn: asyncpg.Connection, table: str) -> int:
    return int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}"))


async def _upsert_positions(sqlite_conn: sqlite3.Connection, pg_conn: asyncpg.Connection, batch_size: int) -> int:
    query = """
        INSERT INTO positions (id, fen_norm)
        VALUES ($1, $2)
        ON CONFLICT (id) DO UPDATE
        SET fen_norm = EXCLUDED.fen_norm
    """
    total = 0
    for batch in _iter_rows(
        sqlite_conn,
        "SELECT id, fen_norm FROM positions ORDER BY id",
        batch_size,
    ):
        params = [(int(row["id"]), row["fen_norm"]) for row in batch]
        await pg_conn.executemany(query, params)
        total += len(params)
    return total


async def _upsert_games(sqlite_conn: sqlite3.Connection, pg_conn: asyncpg.Connection, batch_size: int) -> int:
    query = """
        INSERT INTO games (
            id, pgn_hash, source_pgn, event, site, date, utc_date, utc_time, white,
            black, result, time_control, white_elo, black_elo, player_color, is_daily,
            termination, eco
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            $10, $11, $12, $13, $14, $15, $16,
            $17, $18
        )
        ON CONFLICT (id) DO UPDATE
        SET pgn_hash = EXCLUDED.pgn_hash,
            source_pgn = EXCLUDED.source_pgn,
            event = EXCLUDED.event,
            site = EXCLUDED.site,
            date = EXCLUDED.date,
            utc_date = EXCLUDED.utc_date,
            utc_time = EXCLUDED.utc_time,
            white = EXCLUDED.white,
            black = EXCLUDED.black,
            result = EXCLUDED.result,
            time_control = EXCLUDED.time_control,
            white_elo = EXCLUDED.white_elo,
            black_elo = EXCLUDED.black_elo,
            player_color = EXCLUDED.player_color,
            is_daily = EXCLUDED.is_daily,
            termination = EXCLUDED.termination,
            eco = EXCLUDED.eco
    """
    total = 0
    for batch in _iter_rows(
        sqlite_conn,
        """
        SELECT id, pgn_hash, source_pgn, event, site, date, utc_date, utc_time, white,
               black, result, time_control, white_elo, black_elo, player_color, is_daily,
               termination, eco
        FROM games
        ORDER BY id
        """,
        batch_size,
    ):
        params = [
            (
                int(row["id"]),
                row["pgn_hash"],
                row["source_pgn"],
                row["event"],
                row["site"],
                row["date"],
                row["utc_date"],
                row["utc_time"],
                row["white"],
                row["black"],
                row["result"],
                row["time_control"],
                row["white_elo"],
                row["black_elo"],
                row["player_color"],
                int(row["is_daily"] or 0),
                row["termination"],
                row["eco"],
            )
            for row in batch
        ]
        await pg_conn.executemany(query, params)
        total += len(params)
    return total


async def _upsert_game_positions(sqlite_conn: sqlite3.Connection, pg_conn: asyncpg.Connection, batch_size: int) -> int:
    query = """
        INSERT INTO game_positions (
            game_id, ply, pos_id, san_move, uci_move, clock_seconds, time_spent_seconds,
            time_spent_fraction, is_self, repertoire_class
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (game_id, ply) DO UPDATE
        SET pos_id = EXCLUDED.pos_id,
            san_move = EXCLUDED.san_move,
            uci_move = EXCLUDED.uci_move,
            clock_seconds = EXCLUDED.clock_seconds,
            time_spent_seconds = EXCLUDED.time_spent_seconds,
            time_spent_fraction = EXCLUDED.time_spent_fraction,
            is_self = EXCLUDED.is_self,
            repertoire_class = EXCLUDED.repertoire_class
    """
    total = 0
    for batch in _iter_rows(
        sqlite_conn,
        """
        SELECT game_id, ply, pos_id, san_move, uci_move, clock_seconds, time_spent_seconds,
               time_spent_fraction, is_self, repertoire_class
        FROM game_positions
        ORDER BY game_id, ply
        """,
        batch_size,
    ):
        params = [
            (
                int(row["game_id"]),
                int(row["ply"]),
                int(row["pos_id"]),
                row["san_move"],
                row["uci_move"],
                row["clock_seconds"],
                row["time_spent_seconds"],
                row["time_spent_fraction"],
                int(row["is_self"]),
                row["repertoire_class"],
            )
            for row in batch
        ]
        await pg_conn.executemany(query, params)
        total += len(params)
    return total


async def _upsert_matches(sqlite_conn: sqlite3.Connection, pg_conn: asyncpg.Connection, batch_size: int) -> int:
    query = """
        INSERT INTO matches (
            game_id, matched_line_id, matching_mode, max_matched_ply, deviation_ply_you,
            deviation_ply_opp, compliance, who_left_first, recovered_to_rep, opponent_dev_to_known,
            tags_json, tie_lines_json
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb)
        ON CONFLICT (game_id) DO UPDATE
        SET matched_line_id = EXCLUDED.matched_line_id,
            matching_mode = EXCLUDED.matching_mode,
            max_matched_ply = EXCLUDED.max_matched_ply,
            deviation_ply_you = EXCLUDED.deviation_ply_you,
            deviation_ply_opp = EXCLUDED.deviation_ply_opp,
            compliance = EXCLUDED.compliance,
            who_left_first = EXCLUDED.who_left_first,
            recovered_to_rep = EXCLUDED.recovered_to_rep,
            opponent_dev_to_known = EXCLUDED.opponent_dev_to_known,
            tags_json = EXCLUDED.tags_json,
            tie_lines_json = EXCLUDED.tie_lines_json
    """
    total = 0
    for batch in _iter_rows(
        sqlite_conn,
        """
        SELECT game_id, matched_line_id, matching_mode, max_matched_ply, deviation_ply_you,
               deviation_ply_opp, compliance, who_left_first, recovered_to_rep, opponent_dev_to_known,
               tags_json, tie_lines_json
        FROM matches
        ORDER BY game_id
        """,
        batch_size,
    ):
        params = [
            (
                int(row["game_id"]),
                row["matched_line_id"],
                row["matching_mode"],
                row["max_matched_ply"],
                row["deviation_ply_you"],
                row["deviation_ply_opp"],
                row["compliance"],
                row["who_left_first"],
                int(row["recovered_to_rep"] or 0),
                int(row["opponent_dev_to_known"] or 0),
                _normalize_jsonb(row["tags_json"]),
                _normalize_jsonb(row["tie_lines_json"]),
            )
            for row in batch
        ]
        await pg_conn.executemany(query, params)
        total += len(params)
    return total


async def _upsert_analysis_ply(sqlite_conn: sqlite3.Connection, pg_conn: asyncpg.Connection, batch_size: int) -> int:
    query = """
        INSERT INTO analysis_ply (
            game_id, ply, pos_id, pre_eval_cp, post_eval_cp, best_uci, your_cpl, rep_cpl, quality_label
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (game_id, ply) DO UPDATE
        SET pos_id = EXCLUDED.pos_id,
            pre_eval_cp = EXCLUDED.pre_eval_cp,
            post_eval_cp = EXCLUDED.post_eval_cp,
            best_uci = EXCLUDED.best_uci,
            your_cpl = EXCLUDED.your_cpl,
            rep_cpl = EXCLUDED.rep_cpl,
            quality_label = EXCLUDED.quality_label
    """
    total = 0
    for batch in _iter_rows(
        sqlite_conn,
        """
        SELECT game_id, ply, pos_id, pre_eval_cp, post_eval_cp, best_uci, your_cpl, rep_cpl, quality_label
        FROM analysis_ply
        ORDER BY game_id, ply
        """,
        batch_size,
    ):
        params = [
            (
                int(row["game_id"]),
                int(row["ply"]),
                int(row["pos_id"]),
                row["pre_eval_cp"],
                row["post_eval_cp"],
                row["best_uci"],
                row["your_cpl"],
                row["rep_cpl"],
                row["quality_label"],
            )
            for row in batch
        ]
        await pg_conn.executemany(query, params)
        total += len(params)
    return total


async def _spot_check_ids(
    sqlite_conn: sqlite3.Connection,
    pg_conn: asyncpg.Connection,
    table: str,
    key_columns: tuple[str, ...],
    sample_size: int = 5,
) -> tuple[int, int]:
    columns_csv = ", ".join(key_columns)
    rows = sqlite_conn.execute(
        f"SELECT {columns_csv} FROM {table} ORDER BY {columns_csv} LIMIT ?",
        (sample_size,),
    ).fetchall()
    if not rows:
        return 0, 0

    matched = 0
    for row in rows:
        predicates = []
        params = []
        for idx, column in enumerate(key_columns, start=1):
            predicates.append(f"{column} = ${idx}")
            params.append(row[column])
        where_clause = " AND ".join(predicates)
        found = await pg_conn.fetchval(
            f"SELECT 1 FROM {table} WHERE {where_clause} LIMIT 1",
            *params,
        )
        if found:
            matched += 1
    return len(rows), matched


async def run_backfill(
    sqlite_path: str,
    postgres_dsn: str,
    batch_size: int,
    skip_if_missing: bool,
) -> None:
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        if skip_if_missing:
            print(f"SQLite file not found at {sqlite_file}. Skipping backfill.")
            return
        raise RuntimeError(f"SQLite file not found: {sqlite_file}")

    sqlite_conn = _connect_sqlite(str(sqlite_file))
    pg_conn = await asyncpg.connect(postgres_dsn)
    try:
        missing = await db.missing_tables(pg_conn, db.REQUIRED_ANALYSIS_TABLES)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(
                "Target Postgres schema is incomplete. "
                f"Missing table(s): {missing_csv}. "
                "Run `python -m backend.bootstrap_postgres_schema` first."
            )

        tables = ("positions", "games", "game_positions", "matches", "analysis_ply")
        sqlite_counts = {table: _sqlite_count(sqlite_conn, table) for table in tables}
        before_counts = {table: await _postgres_count(pg_conn, table) for table in tables}

        print("Source counts (SQLite):")
        for table in tables:
            print(f"  {table}: {sqlite_counts[table]}")

        print("Target counts before backfill (Postgres):")
        for table in tables:
            print(f"  {table}: {before_counts[table]}")

        print("Backfilling positions...")
        inserted_positions = await _upsert_positions(sqlite_conn, pg_conn, batch_size)
        print(f"  upserted rows: {inserted_positions}")

        print("Backfilling games...")
        inserted_games = await _upsert_games(sqlite_conn, pg_conn, batch_size)
        print(f"  upserted rows: {inserted_games}")

        print("Backfilling game_positions...")
        inserted_game_positions = await _upsert_game_positions(sqlite_conn, pg_conn, batch_size)
        print(f"  upserted rows: {inserted_game_positions}")

        print("Backfilling matches...")
        inserted_matches = await _upsert_matches(sqlite_conn, pg_conn, batch_size)
        print(f"  upserted rows: {inserted_matches}")

        print("Backfilling analysis_ply...")
        inserted_analysis = await _upsert_analysis_ply(sqlite_conn, pg_conn, batch_size)
        print(f"  upserted rows: {inserted_analysis}")

        after_counts = {table: await _postgres_count(pg_conn, table) for table in tables}
        print("Target counts after backfill (Postgres):")
        for table in tables:
            print(f"  {table}: {after_counts[table]}")

        print("Spot checks:")
        for table, keys in (
            ("positions", ("id",)),
            ("games", ("id",)),
            ("game_positions", ("game_id", "ply")),
            ("matches", ("game_id",)),
            ("analysis_ply", ("game_id", "ply")),
        ):
            sample_total, sample_matched = await _spot_check_ids(
                sqlite_conn,
                pg_conn,
                table,
                keys,
                sample_size=5,
            )
            print(f"  {table}: matched {sample_matched}/{sample_total} sampled keys")
    finally:
        sqlite_conn.close()
        await pg_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill SQLite analysis data into PostgreSQL (idempotent upserts)."
    )
    parser.add_argument(
        "--sqlite-path",
        default=SETTINGS.sqlite_path,
        help="Path to SQLite database file (defaults to SQLITE_PATH env).",
    )
    parser.add_argument(
        "--dsn",
        default=SETTINGS.postgres_dsn,
        help="Postgres DSN (defaults to POSTGRES_DSN env).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for upserts.",
    )
    parser.add_argument(
        "--skip-if-missing",
        action="store_true",
        help="Exit successfully when SQLite file is missing.",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        raise RuntimeError("batch-size must be >= 1")

    asyncio.run(
        run_backfill(
            sqlite_path=args.sqlite_path,
            postgres_dsn=args.dsn,
            batch_size=args.batch_size,
            skip_if_missing=args.skip_if_missing,
        )
    )
    print("Backfill complete.")


if __name__ == "__main__":
    main()
