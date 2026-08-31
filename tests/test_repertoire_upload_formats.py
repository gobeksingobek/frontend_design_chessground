from __future__ import annotations

import io
import zipfile

import pytest

from backend.repertoire_import import parse_repertoire_upload


PGN = b'[Event "Line"]\n\n1. e4 e5 2. Nf3 *\n'


def test_single_pgn_and_zip_are_supported() -> None:
    assert parse_repertoire_upload(PGN, "line.pgn")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("nested/line.pgn", PGN)
    assert parse_repertoire_upload(buffer.getvalue(), "lines.zip")


def test_database_snapshots_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse_repertoire_upload(b"snapshot", "legacy.db")
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse_repertoire_upload(b"dump", "legacy.sql")
