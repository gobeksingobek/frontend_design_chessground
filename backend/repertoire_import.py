from __future__ import annotations

import io
import zipfile
import json
from pathlib import Path

import asyncpg
import chess

from analysis.position_utils import normalize_fen
from parsing import repertoire_loader
from parsing.repertoire_identity import canonical_path_hash


def parse_repertoire_upload(
    payload: bytes, filename: str, player_names: list[str] | None = None
) -> list[dict]:
    suffix = Path(filename or "upload").suffix.lower()
    if suffix == ".pgn":
        return repertoire_loader.load_repertoire_pgn_text(
            payload.decode("utf-8", errors="replace"), filename or "upload.pgn", player_names
        )
    if suffix != ".zip":
        raise ValueError("Unsupported file format. Upload a .zip archive of PGNs or a single .pgn file.")
    lines: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if Path(name).suffix.lower() == ".pgn"]
            for name in sorted(names):
                lines.extend(
                    repertoire_loader.load_repertoire_pgn_text(
                        archive.read(name).decode("utf-8", errors="replace"),
                        name,
                        player_names,
                    )
                )
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded zip payload is invalid or corrupted.") from exc
    if not lines:
        raise ValueError("No PGN files were found in upload payload.")
    return lines


async def ingest_repertoire_lines_postgres(
    conn: asyncpg.Connection, parsed_lines: list[dict], workspace_id: str
) -> tuple[int, int, int]:
    """Persist uploaded repertoire lines directly to the canonical Postgres schema."""
    inserted = 0
    duplicates = 0
    for line in parsed_lines:
        moves = list(line.get("moves") or [])
        moves_uci = [str(move.get("uci") or "") for move in moves]
        side_to_play = str(line.get("side_to_play") or "white")
        root_key = str(line.get("root_key") or "root")
        path_hash = canonical_path_hash(root_key, moves_uci, side_to_play)
        line_id = f"{root_key.strip().lower() or 'root'}-{path_hash[:16]}"
        existing = await conn.fetchval(
            "SELECT 1 FROM repertoire_lines WHERE workspace_id = $1::uuid AND canonical_path_hash = $2",
            workspace_id,
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
                workspace_id, line_id, canonical_path_hash, source_pgn,
                is_priority, side_to_play, metadata_json
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            workspace_id,
            line_id,
            path_hash,
            line.get("source_pgn"),
            1 if line.get("is_priority") else 0,
            side_to_play,
            json.dumps({"label": line.get("label") or line_id}),
        )
        await conn.execute(
            """
            INSERT INTO repertoire_compact(
                workspace_id, line_id, moves_json, san_moves_json, pos_ids_json, ply_count
            ) VALUES ($1::uuid, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6)
            """,
            workspace_id,
            line_id,
            json.dumps(moves_uci),
            json.dumps(san_moves),
            json.dumps(pos_ids),
            len(moves_uci),
        )
        for index, uci in enumerate(moves_uci):
            await conn.execute(
                """
                INSERT INTO repertoire_edges(
                    workspace_id, pos_id, uci_move, san_move, next_pos_id, weight, is_priority_edge
                ) VALUES ($1::uuid, $2, $3, $4, $5, 1, $6)
                ON CONFLICT (workspace_id, pos_id, uci_move, next_pos_id) DO UPDATE
                SET weight = repertoire_edges.weight + 1,
                    is_priority_edge = GREATEST(repertoire_edges.is_priority_edge, EXCLUDED.is_priority_edge)
                """,
                workspace_id,
                pos_ids[index],
                uci,
                san_moves[index],
                pos_ids[index + 1],
                1 if line.get("is_priority") else 0,
            )
        await conn.execute(
            """
            INSERT INTO trainer_line_state(workspace_id, line_id, side_to_play)
            VALUES ($1::uuid, $2, $3)
            ON CONFLICT (workspace_id, line_id) DO NOTHING
            """,
            workspace_id,
            line_id,
            side_to_play,
        )
        inserted += 1
    return inserted, duplicates, len(parsed_lines)
