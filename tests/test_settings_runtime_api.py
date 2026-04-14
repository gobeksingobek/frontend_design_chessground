from __future__ import annotations

from pathlib import Path

from backend.read_api import get_runtime_settings_payload, save_runtime_settings_payload


def _write_ini(path: Path) -> None:
    path.write_text(
        """
[PATHS]
repertoire_dir = /rep
games_dir = /games
database_path = /db.sqlite
stockfish_path = /bin/stockfish
piece_dir = /pieces

[ANALYSIS]
engine_depth = 18
max_plies = 28
engine_threads = 2
engine_hash_mb = 32
engine_max_time_ms = 450

[PLAYER]
name = alice
player_names = alice, ali
rating_band_size = 100

[FETCH]
chesscom_usernames = alicecc
lichess_usernames = alicelc
variants = blitz,rapid
days_back = 120
""".strip(),
        encoding="utf-8",
    )


def test_settings_runtime_round_trip_for_desktop_groups(tmp_path: Path) -> None:
    ini_path = tmp_path / "settings.ini"
    _write_ini(ini_path)

    current = get_runtime_settings_payload(ini_path)
    assert current["games_dir"] == "/games"
    assert current["engine_depth"] == 18
    assert current["player_name"] == "alice"
    assert current["variants"] == ["blitz", "rapid"]

    payload = {
        "chesscom_usernames": ["alicecc", "alicecc"],
        "lichess_usernames": ["alicelc"],
        "variants": ["Rapid", "Blitz"],
        "days_back": 90,
        "games_dir": "/new-games",
        "database_path": "/new-db.sqlite",
        "repertoire_dir": "/new-rep",
        "stockfish_path": "/new-stockfish",
        "piece_dir": "/new-pieces",
        "engine_depth": 20,
        "max_plies": 30,
        "engine_threads": 3,
        "engine_hash_mb": 64,
        "engine_max_time_ms": 700,
        "player_name": "bob",
        "player_names": ["bob", "bobby"],
    }
    saved, errors = save_runtime_settings_payload(ini_path, payload)

    assert errors == []
    assert saved is not None
    assert saved["variants"] == ["rapid", "blitz"]
    assert saved["games_dir"] == "/new-games"
    assert saved["player_name"] == "bob"


def test_settings_runtime_validation_errors_include_codes(tmp_path: Path) -> None:
    ini_path = tmp_path / "settings.ini"
    _write_ini(ini_path)

    saved, errors = save_runtime_settings_payload(
        ini_path,
        {
            "chesscom_usernames": "not-a-list",
            "lichess_usernames": [],
            "variants": [],
            "days_back": 0,
            "engine_depth": "deep",
        },
    )

    assert saved is None
    by_field = {error.field: error for error in errors}
    assert by_field["chesscom_usernames"].code == "type"
    assert by_field["variants"].code == "min_items"
    assert by_field["days_back"].code == "range"
    assert by_field["engine_depth"].code == "type"
