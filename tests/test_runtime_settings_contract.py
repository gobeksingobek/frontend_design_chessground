from __future__ import annotations

from backend.settings import DEFAULT_RUNTIME_SETTINGS, merge_runtime_settings_payload


def test_workspace_settings_accept_analysis_and_fetch_fields() -> None:
    saved, errors = merge_runtime_settings_payload(
        DEFAULT_RUNTIME_SETTINGS,
        {"engine_depth": 18, "variants": ["rapid", "blitz"], "player_names": ["Alice"]},
    )
    assert errors == []
    assert saved is not None
    assert saved["engine_depth"] == 18


def test_client_and_worker_paths_are_not_workspace_settings() -> None:
    saved, errors = merge_runtime_settings_payload(
        DEFAULT_RUNTIME_SETTINGS,
        {"database_path": "legacy", "stockfish_path": "local", "piece_dir": "pieces"},
    )
    assert saved is None
    assert {error.field for error in errors} == {"database_path", "stockfish_path", "piece_dir"}
