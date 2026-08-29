from __future__ import annotations

import sqlite3

from analysis.game_fetcher import _variant_set
from backend.settings import merge_runtime_settings_payload
from storage import database, queries


def test_existing_game_hashes_reads_persisted_sqlite_games() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(database.SCHEMA_SQL.format(version=database.EXPECTED_SCHEMA_VERSION))
    conn.execute("INSERT INTO games(pgn_hash, is_daily) VALUES (?, 0)", ("known-hash",))
    conn.commit()
    assert queries.fetch_existing_game_hashes(conn) == {"known-hash"}


def test_fetch_variants_include_bullet_and_filter_unknown_values() -> None:
    assert _variant_set(["Bullet", "blitz", "unknown"]) == {"bullet", "blitz"}


def test_runtime_settings_reject_unsupported_fetch_variants() -> None:
    saved, errors = merge_runtime_settings_payload(
        {
            "chesscom_usernames": ["alice"],
            "lichess_usernames": [],
            "variants": ["blitz"],
            "player_names": ["alice"],
            "days_back": 30,
        },
        {"variants": ["ultrabullet"]},
    )
    assert saved is None
    assert [(error.field, error.code) for error in errors] == [("variants", "unsupported_variant")]
