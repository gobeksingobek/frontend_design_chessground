from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import asyncpg
import chess

from analysis.position_utils import normalize_fen
from analysis import game_fetcher
from backend import repertoire_import
from parsing import clock_parser, game_loader
from parsing.game_identity import compute_game_hash


def _safe_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


async def _load_artifact(conn: asyncpg.Connection, artifact_id: str, workspace_id: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        "SELECT * FROM source_artifacts WHERE id = $1::uuid AND workspace_id = $2::uuid",
        artifact_id,
        workspace_id,
    )
    if row is None:
        raise ValueError(f"Source artifact {artifact_id} was not found.")
    return row


async def _ingest_game_artifact(
    conn: asyncpg.Connection,
    artifact: asyncpg.Record,
    workspace_id: str,
    player_names: list[str],
) -> dict[str, Any]:
    if not player_names:
        raise ValueError("Configure player_name or player_names before importing games.")
    parsed_games = game_loader.load_games_from_pgn_text(
        str(artifact["pgn_text"]), player_names, f"artifact://{artifact['id']}"
    )
    inserted = 0
    duplicates = 0
    for game in parsed_games:
        tags = game["tags"]
        pgn_hash = compute_game_hash(tags, game["moves_uci"])
        game_id = await conn.fetchval(
            """
            INSERT INTO games(
                workspace_id, source_artifact_id, pgn_hash, source_pgn, event, site,
                date, utc_date, utc_time, white, black, result, time_control,
                white_elo, black_elo, player_color, is_daily, termination, eco
            ) VALUES (
                $1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18, $19
            )
            ON CONFLICT (workspace_id, pgn_hash) DO NOTHING
            RETURNING id
            """,
            workspace_id,
            artifact["id"],
            pgn_hash,
            f"artifact://{artifact['id']}",
            tags.get("Event"), tags.get("Site"), game.get("date"), tags.get("UTCDate"),
            tags.get("UTCTime"), tags.get("White"), tags.get("Black"), tags.get("Result"),
            game.get("time_control"), _safe_int(tags.get("WhiteElo")), _safe_int(tags.get("BlackElo")),
            game.get("player_color"), 1 if game.get("is_daily") else 0, tags.get("Termination"), tags.get("ECO"),
        )
        if game_id is None:
            duplicates += 1
            continue
        inserted += 1
        board = chess.Board()
        base_seconds, _ = clock_parser.parse_time_control(game.get("time_control"))
        for move in game["moves"]:
            pos_id = await conn.fetchval(
                """
                INSERT INTO positions(fen_norm) VALUES ($1)
                ON CONFLICT (fen_norm) DO UPDATE SET fen_norm = EXCLUDED.fen_norm
                RETURNING id
                """,
                normalize_fen(board),
            )
            board.push(chess.Move.from_uci(move["move_uci"]))
            next_pos_id = await conn.fetchval(
                """
                INSERT INTO positions(fen_norm) VALUES ($1)
                ON CONFLICT (fen_norm) DO UPDATE SET fen_norm = EXCLUDED.fen_norm
                RETURNING id
                """,
                normalize_fen(board),
            )
            time_spent = move.get("time_spent_seconds")
            fraction = time_spent / base_seconds if base_seconds and time_spent is not None else None
            await conn.execute(
                """
                INSERT INTO game_positions(
                    workspace_id, game_id, ply, pos_id, next_pos_id, san_move, uci_move,
                    clock_seconds, time_spent_seconds, time_spent_fraction, is_self
                ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                workspace_id, game_id, move["ply"], pos_id, next_pos_id, move.get("move_san"),
                move.get("move_uci"), move.get("clock_seconds"), time_spent, fraction,
                1 if move.get("is_self") else 0,
            )
    return {"games_inserted": inserted, "games_duplicate": duplicates, "games_parsed": len(parsed_games)}


async def execute_ingest_step(conn: asyncpg.Connection, step: dict[str, Any]) -> dict[str, Any]:
    payload = step["payload"]
    workspace_id = step["workspace_id"]
    if step["step_type"] == "provider-fetch":
        settings_row = await conn.fetchrow(
            "SELECT payload FROM runtime_settings WHERE workspace_id = $1::uuid",
            workspace_id,
        )
        runtime = settings_row["payload"] if settings_row else {}
        if isinstance(runtime, str):
            runtime = json.loads(runtime)
        chesscom = list(runtime.get("chesscom_usernames") or [])
        lichess = list(runtime.get("lichess_usernames") or [])
        if not chesscom and not lichess:
            raise ValueError("Configure at least one Chess.com or Lichess username before fetching games.")
        batches: list[tuple[str, str, list[str]]] = []

        def collect(provider: str, username: str, pgn_chunks: list[str]) -> None:
            batches.append((provider, username, pgn_chunks))

        existing = {
            str(row["pgn_hash"])
            for row in await conn.fetch(
                "SELECT pgn_hash FROM games WHERE workspace_id = $1::uuid", workspace_id
            )
        }
        summaries = await asyncio.to_thread(
            game_fetcher.fetch_games,
            games_dir=Path("."),
            chesscom_usernames=chesscom,
            lichess_usernames=lichess,
            variants=list(runtime.get("variants") or ["bullet", "blitz", "rapid", "daily"]),
            days_back=int(runtime.get("days_back") or 90),
            state_path=None,
            existing_pgn_hashes=existing,
            write_files=False,
            on_new_games=collect,
        )
        totals = {"sources_persisted": 0, "games_inserted": 0, "games_duplicate": 0, "games_parsed": 0}
        for provider, username, chunks in batches:
            for index, pgn_text in enumerate(chunks):
                content_hash = hashlib.sha256(pgn_text.encode("utf-8")).hexdigest()
                artifact_id = await conn.fetchval(
                    """
                    INSERT INTO source_artifacts(
                        id, workspace_id, source_type, provider, original_name,
                        content_hash, pgn_text, metadata_json
                    ) VALUES (gen_random_uuid(), $1::uuid, 'game', $2, $3, $4, $5, $6::jsonb)
                    ON CONFLICT (workspace_id, source_type, content_hash) DO UPDATE
                    SET updated_at = NOW()
                    RETURNING id
                    """,
                    workspace_id,
                    provider,
                    f"{provider}-{username}-{index}.pgn",
                    content_hash,
                    pgn_text,
                    json.dumps({"username": username}),
                )
                totals["sources_persisted"] += 1
                artifact = await _load_artifact(conn, str(artifact_id), workspace_id)
                player_names = [
                    str(value) for value in [
                        runtime.get("player_name"), *(runtime.get("player_names") or []),
                        *chesscom, *lichess,
                    ] if value
                ]
                ingested = await _ingest_game_artifact(
                    conn, artifact, workspace_id, list(dict.fromkeys(player_names))
                )
                for key in ("games_inserted", "games_duplicate", "games_parsed"):
                    totals[key] += int(ingested[key])
        return {**totals, "fetches": [summary.__dict__ for summary in summaries]}
    artifact = await _load_artifact(conn, str(payload["source_artifact_id"]), workspace_id)
    if step["step_type"] == "repertoire-import":
        settings_row = await conn.fetchrow(
            "SELECT payload FROM runtime_settings WHERE workspace_id=$1::uuid", workspace_id
        )
        runtime = settings_row["payload"] if settings_row else {}
        if isinstance(runtime, str):
            runtime = json.loads(runtime)
        parsed = repertoire_import.parse_repertoire_upload(
            str(artifact["pgn_text"]).encode("utf-8"),
            "source-artifact.pgn",
            [
                str(value) for value in [
                    runtime.get("player_name"), *(runtime.get("player_names") or [])
                ] if value
            ],
        )
        inserted, duplicates, total = await repertoire_import.ingest_repertoire_lines_postgres(
            conn, parsed, workspace_id
        )
        return {"inserted_lines": inserted, "duplicate_lines": duplicates, "total_lines": total}
    if step["step_type"] == "game-import":
        names = payload.get("player_names") or []
        if not isinstance(names, list):
            raise ValueError("player_names must be a list")
        return await _ingest_game_artifact(conn, artifact, workspace_id, [str(name) for name in names])
    raise ValueError(f"Unsupported ingest step: {step['step_type']}")
