from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

from backend import repertoire_import
from storage import database


def _sample_pgn() -> bytes:
    return b'''[Event "Import Test"]\n[White "You"]\n[Black "Opponent"]\n\n1. e4 e5 2. Nf3 Nc6 *\n'''


def _zipped_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("repertoire/main.pgn", _sample_pgn())
    return buffer.getvalue()


def test_repertoire_import_successful_zip() -> None:
    parsed = repertoire_import.parse_repertoire_upload(_zipped_payload(), "bundle.zip")
    assert len(parsed) == 1
    assert parsed[0]["moves"][0]["uci"] == "e2e4"


def test_repertoire_import_malformed_upload() -> None:
    try:
        repertoire_import.parse_repertoire_upload(b"not-a-valid-zip", "broken.zip")
    except ValueError as exc:
        assert "invalid or corrupted" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for malformed zip upload")


def test_repertoire_import_duplicate_handling() -> None:
    parsed = repertoire_import.parse_repertoire_upload(_zipped_payload(), "bundle.zip")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "analysis.db"
        conn = database.ensure_db(str(db_path), reset_on_mismatch=True)
        try:
            first_inserted, first_duplicates, first_total = repertoire_import.ingest_repertoire_lines(conn, parsed)
            second_inserted, second_duplicates, second_total = repertoire_import.ingest_repertoire_lines(conn, parsed)
        finally:
            conn.close()

    assert (first_inserted, first_duplicates, first_total) == (1, 0, 1)
    assert (second_inserted, second_duplicates, second_total) == (0, 1, 1)
