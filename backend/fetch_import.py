from __future__ import annotations

from typing import Iterable

import asyncpg
import chess

from analysis.position_utils import normalize_fen
from parsing import clock_parser, game_loader
from storage import queries


async def fetch_existing_game_hashes(pool: asyncpg.Pool) -> set[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT pgn_hash FROM games WHERE pgn_hash IS NOT NULL AND pgn_hash <> ''"
        )
    return {str(row["pgn_hash"]) for row in rows}


async def persist_fetched_games(
    pool: asyncpg.Pool,
    batches: Iterable[tuple[str, str, list[str]]],
    player_names: list[str],
) -> dict[str, int]:
    """Persist downloaded PGNs and normalized move data directly in PostgreSQL.

    Remote source rows are retained even when a game already exists from a prior
    import.  This makes provider fetches idempotent while keeping the raw input
    available for later analysis work.
    """
    totals = {"sources_persisted": 0, "games_persisted": 0, "games_unmatched": 0}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for provider, username, pgn_chunks in batches:
                for pgn_text in pgn_chunks:
                    parsed_games = game_loader.load_games_from_pgn_text(
                        pgn_text,
                        player_names,
                        f"remote://{provider}/{username}",
                    )
                    if len(parsed_games) != 1:
                        totals["games_unmatched"] += 1
                        continue

                    game = parsed_games[0]
                    pgn_hash = queries.compute_game_hash(game["tags"], game["moves_uci"])
                    source_pgn = f"remote://{provider}/{username}/{pgn_hash}.pgn"
                    source_inserted = await conn.fetchval(
                        """
                        INSERT INTO fetched_game_sources(pgn_hash, provider, username, pgn_text)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (pgn_hash) DO NOTHING
                        RETURNING 1
                        """,
                        pgn_hash,
                        provider,
                        username,
                        pgn_text,
                    )
                    if source_inserted:
                        totals["sources_persisted"] += 1

                    tags = game["tags"]
                    game_id = await conn.fetchval(
                        """
                        INSERT INTO games (
                            pgn_hash, source_pgn, event, site, date, utc_date, utc_time, white,
                            black, result, time_control, white_elo, black_elo, player_color,
                            is_daily, termination, eco
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                            $15, $16, $17
                        )
                        ON CONFLICT (pgn_hash) DO NOTHING
                        RETURNING id
                        """,
                        pgn_hash,
                        source_pgn,
                        tags.get("Event"),
                        tags.get("Site"),
                        game.get("date"),
                        tags.get("UTCDate"),
                        tags.get("UTCTime"),
                        tags.get("White"),
                        tags.get("Black"),
                        tags.get("Result"),
                        game.get("time_control"),
                        _safe_int(tags.get("WhiteElo")),
                        _safe_int(tags.get("BlackElo")),
                        game.get("player_color"),
                        1 if game.get("is_daily") else 0,
                        tags.get("Termination"),
                        tags.get("ECO"),
                    )
                    if game_id is None:
                        continue

                    totals["games_persisted"] += 1
                    board = chess.Board()
                    base_seconds, _ = clock_parser.parse_time_control(game.get("time_control"))
                    for move in game["moves"]:
                        pos_id = await conn.fetchval(
                            """
                            INSERT INTO positions(fen_norm)
                            VALUES ($1)
                            ON CONFLICT (fen_norm) DO UPDATE SET fen_norm = EXCLUDED.fen_norm
                            RETURNING id
                            """,
                            normalize_fen(board),
                        )
                        time_spent = move.get("time_spent_seconds")
                        fraction = time_spent / base_seconds if base_seconds and time_spent is not None else None
                        await conn.execute(
                            """
                            INSERT INTO game_positions (
                                game_id, ply, pos_id, san_move, uci_move, clock_seconds,
                                time_spent_seconds, time_spent_fraction, is_self, repertoire_class
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL)
                            """,
                            game_id,
                            move["ply"],
                            pos_id,
                            move.get("move_san"),
                            move.get("move_uci"),
                            move.get("clock_seconds"),
                            time_spent,
                            fraction,
                            1 if move.get("is_self") else 0,
                        )
                        board.push(chess.Move.from_uci(move["move_uci"]))
    return totals


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
