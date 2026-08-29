from __future__ import annotations

import tempfile
import zipfile
import json
from pathlib import Path
import sqlite3

import asyncpg
import chess

from analysis import pipeline as analysis_pipeline
from analysis.position_utils import normalize_fen
from parsing import repertoire_loader
from storage import line_ids


def parse_repertoire_upload(payload: bytes, filename: str) -> list[dict]:
    suffix = Path(filename or "upload").suffix.lower()
    with tempfile.TemporaryDirectory(prefix="rep-import-") as tmpdir:
        root = Path(tmpdir)
        if suffix == ".zip":
            archive_path = root / "upload.zip"
            archive_path.write_bytes(payload)
            try:
                with zipfile.ZipFile(archive_path) as zf:
                    zf.extractall(root / "content")
            except zipfile.BadZipFile as exc:
                raise ValueError("Uploaded zip payload is invalid or corrupted.") from exc
            parse_root = root / "content"
        elif suffix == ".pgn":
            parse_root = root / "content"
            parse_root.mkdir(parents=True, exist_ok=True)
            (parse_root / (filename or "upload.pgn")).write_bytes(payload)
        else:
            raise ValueError("Unsupported file format. Upload a .zip archive of PGNs or a single .pgn file.")

        pgn_files = list(parse_root.rglob("*.pgn")) + list(parse_root.rglob("*.PGN"))
        if not pgn_files:
            raise ValueError("No PGN files were found in upload payload.")

        return repertoire_loader.load_repertoire_lines(str(parse_root), sorted(set(pgn_files)))


def ingest_repertoire_lines(conn: sqlite3.Connection, parsed_lines: list[dict]) -> tuple[int, int, int]:
    position_store = analysis_pipeline.PositionStore(conn)
    inserted = 0
    duplicates = 0
    for line in parsed_lines:
        moves_uci = [str(move.get("uci") or "") for move in line.get("moves", [])]
        side_to_play = str(line.get("side_to_play") or "white")
        root_key = str(line.get("root_key") or "root")
        path_hash = line_ids.canonical_path_hash(root_key, moves_uci, side_to_play)

        existing = conn.execute(
            "SELECT line_id FROM repertoire_lines WHERE canonical_path_hash = ?",
            (path_hash,),
        ).fetchone()
        if existing:
            duplicates += 1
            continue

        analysis_pipeline._insert_repertoire_lines(conn, position_store, [line])
        inserted += 1

    if inserted:
        analysis_pipeline._build_repertoire_edges(conn)
        analysis_pipeline._ensure_trainer_state(conn)

    return inserted, duplicates, len(parsed_lines)


async def ingest_repertoire_lines_postgres(
    conn: asyncpg.Connection, parsed_lines: list[dict]
) -> tuple[int, int, int]:
    """Persist uploaded repertoire lines directly to the canonical Postgres schema."""
    inserted = 0
    duplicates = 0
    for line in parsed_lines:
        moves = list(line.get("moves") or [])
        moves_uci = [str(move.get("uci") or "") for move in moves]
        side_to_play = str(line.get("side_to_play") or "white")
        root_key = str(line.get("root_key") or "root")
        path_hash = line_ids.canonical_path_hash(root_key, moves_uci, side_to_play)
        line_id = f"{root_key.strip().lower() or 'root'}-{path_hash[:16]}"
        existing = await conn.fetchval(
            "SELECT 1 FROM repertoire_lines WHERE canonical_path_hash = $1",
            path_hash,
        )
        if existing:
            duplicates += 1
            continue

        board = chess.Board()
        pos_ids: list[int] = []
        san_moves: list[str] = []
        for move in moves:
            pos_id = await conn.fetchval(
                """
                INSERT INTO positions(fen_norm) VALUES ($1)
                ON CONFLICT (fen_norm) DO UPDATE SET fen_norm = EXCLUDED.fen_norm
                RETURNING id
                """,
                normalize_fen(board),
            )
            pos_ids.append(int(pos_id))
            uci = str(move.get("uci") or "")
            san_moves.append(str(move.get("san") or ""))
            board.push(chess.Move.from_uci(uci))
        final_pos_id = await conn.fetchval(
            """
            INSERT INTO positions(fen_norm) VALUES ($1)
            ON CONFLICT (fen_norm) DO UPDATE SET fen_norm = EXCLUDED.fen_norm
            RETURNING id
            """,
            normalize_fen(board),
        )
        pos_ids.append(int(final_pos_id))
        await conn.execute(
            """
            INSERT INTO repertoire_lines(
                line_id, canonical_path_hash, source_pgn, is_priority, side_to_play, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            line_id,
            path_hash,
            line.get("source_pgn"),
            1 if line.get("is_priority") else 0,
            side_to_play,
            json.dumps({"label": line.get("label") or line_id}),
        )
        await conn.execute(
            """
            INSERT INTO repertoire_compact(line_id, moves_json, san_moves_json, pos_ids_json, ply_count)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5)
            """,
            line_id,
            json.dumps(moves_uci),
            json.dumps(san_moves),
            json.dumps(pos_ids),
            len(moves_uci),
        )
        inserted += 1
    return inserted, duplicates, len(parsed_lines)
