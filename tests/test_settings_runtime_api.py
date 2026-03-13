from backend.api_service import RuntimeSettingsUpdateRequest


def test_settings_runtime_schema_accepts_core_fields() -> None:
    payload = RuntimeSettingsUpdateRequest(days_back=30, chesscom_usernames=[], lichess_usernames=[], variants=["rapid"], engine_depth=18)
    assert payload.days_back == 30
    assert payload.engine_depth == 18
