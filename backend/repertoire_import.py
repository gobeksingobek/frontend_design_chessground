from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
import sqlite3

from analysis import pipeline as analysis_pipeline
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
