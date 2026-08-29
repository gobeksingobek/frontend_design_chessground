from __future__ import annotations

import asyncio
import sqlite3

import pytest

from analysis.game_fetcher import _variant_set
from backend.settings import merge_runtime_settings_payload
from backend import db
from storage import database, queries


class _FakeConnection:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def fetchrow(self, *_args: object) -> dict[str, object]:
        return {"payload": self.payload}


class _FakeAcquire:
    def __init__(self, payload: object) -> None:
        self.connection = _FakeConnection(payload)

    async def __aenter__(self) -> _FakeConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakePool:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.payload)


def _fetch_runtime_settings(payload: object) -> dict[str, object] | None:
    return asyncio.run(db.fetch_runtime_settings(_FakePool(payload)))  # type: ignore[arg-type]


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


def test_fetched_game_sources_is_required_for_postgres_startup() -> None:
    assert "fetched_game_sources" in db.REQUIRED_ANALYSIS_TABLES


def test_runtime_settings_decodes_asyncpg_json_string() -> None:
    assert _fetch_runtime_settings('{"days_back": 30, "variants": ["bullet"]}') == {
        "days_back": 30,
        "variants": ["bullet"],
    }


def test_runtime_settings_accepts_predecoded_json_mapping() -> None:
    assert _fetch_runtime_settings({"days_back": 14}) == {"days_back": 14}


@pytest.mark.parametrize("payload", ["not-json", "[]", "null", 42])
def test_runtime_settings_rejects_invalid_or_non_object_json(payload: object) -> None:
    with pytest.raises(RuntimeError, match="Persisted runtime settings"):
        _fetch_runtime_settings(payload)
