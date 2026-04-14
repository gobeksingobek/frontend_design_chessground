from __future__ import annotations

import configparser
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_render_environment() -> bool:
    return bool(os.getenv("RENDER")) or bool(os.getenv("RENDER_SERVICE_ID"))


def _is_production_environment() -> bool:
    for env_name in ("ENVIRONMENT", "APP_ENV", "PYTHON_ENV"):
        value = os.getenv(env_name)
        if value and value.strip().lower() == "production":
            return True
    return _is_render_environment()


def _default_data_backend() -> str:
    return "postgres"


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


_DEFAULT_API_TOKEN_VALUES = {
    "dev-token",
    "changeme",
    "change-me",
    "default-token",
    "your-token-here",
    "example-token",
}


def is_default_api_token(token: str) -> bool:
    normalized = token.strip().lower()
    return not normalized or normalized in _DEFAULT_API_TOKEN_VALUES


@dataclass(frozen=True)
class BackendSettings:
    is_render_environment: bool = _is_render_environment()
    is_production_environment: bool = _is_production_environment()
    data_backend: str = os.getenv("DATA_BACKEND", _default_data_backend()).strip().lower()
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/chessground")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/analysis.db")
    api_auth_token: str = os.getenv("API_AUTH_TOKEN", "dev-token")
    api_cors_origins: tuple[str, ...] = _parse_csv(os.getenv("API_CORS_ORIGINS"))
    enforce_postgres_on_render: bool = _is_truthy(os.getenv("ENFORCE_POSTGRES_ON_RENDER", "1"))
    stream_name: str = os.getenv("SIDELINE_STREAM_NAME", "sideline:jobs")
    dead_letter_stream: str = os.getenv("SIDELINE_DEAD_LETTER_STREAM", "sideline:jobs:dead")
    consumer_group: str = os.getenv("SIDELINE_CONSUMER_GROUP", "sideline-workers")
    consumer_name: str = os.getenv("SIDELINE_CONSUMER_NAME", "worker-1")
    max_retries: int = int(os.getenv("SIDELINE_MAX_RETRIES", "3"))
    stream_block_ms: int = int(os.getenv("SIDELINE_STREAM_BLOCK_MS", "5000"))
    stockfish_path: str = os.getenv("STOCKFISH_PATH", "stockfish")
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "14"))

    def validate_deployment_config(self) -> None:
        if self.is_production_environment:
            if not self.api_cors_origins:
                raise RuntimeError(
                    "API_CORS_ORIGINS is required in production/Render deployments. "
                    "Set API_CORS_ORIGINS to a comma-separated allow-list of trusted web origins."
                )
            if is_default_api_token(self.api_auth_token):
                raise RuntimeError(
                    "API_AUTH_TOKEN must be set to a non-default secret in production/Render deployments. "
                    "Generate a strong token and set API_AUTH_TOKEN before startup."
                )


SETTINGS = BackendSettings()


@dataclass(frozen=True)
class RuntimeFieldError:
    field: str
    code: str
    message: str


_RUNTIME_LIST_FIELDS = {"chesscom_usernames", "lichess_usernames", "variants", "player_names"}
_RUNTIME_STR_FIELDS = {
    "repertoire_dir",
    "games_dir",
    "database_path",
    "stockfish_path",
    "piece_dir",
    "player_name",
    "matching_mode",
    "engine_mode",
    "engine_profile",
}
_RUNTIME_BOOL_FIELDS = {"enable_engine_cache", "incremental_analysis", "engine_cache_prune_non_active"}
_RUNTIME_INT_FIELDS: dict[str, tuple[int, int | None]] = {
    "days_back": (1, 3650),
    "engine_depth": (1, None),
    "max_plies": (1, None),
    "rating_band_size": (1, None),
    "review_top_n": (1, None),
    "tabiya_top_n": (1, None),
    "engine_workers": (0, None),
    "engine_worker_cap": (1, None),
    "engine_threads": (1, None),
    "engine_hash_mb": (0, None),
    "engine_max_time_ms": (1, None),
    "missing_coverage_proposal_threshold": (1, None),
}
_RUNTIME_REQUIRED_FIELDS = {"chesscom_usernames", "lichess_usernames", "variants", "days_back"}
_RUNTIME_ALLOWED_FIELDS = _RUNTIME_LIST_FIELDS | _RUNTIME_STR_FIELDS | _RUNTIME_BOOL_FIELDS | set(_RUNTIME_INT_FIELDS)


def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _validate_runtime_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[RuntimeFieldError]]:
    normalized: dict[str, Any] = {}
    errors: list[RuntimeFieldError] = []

    unknown_fields = sorted(set(payload) - _RUNTIME_ALLOWED_FIELDS)
    for field in unknown_fields:
        errors.append(RuntimeFieldError(field=field, code="unknown_field", message="Unknown field"))

    for field in sorted(_RUNTIME_REQUIRED_FIELDS):
        if field not in payload:
            errors.append(RuntimeFieldError(field=field, code="required", message="Field is required"))

    for field, value in payload.items():
        if field in _RUNTIME_LIST_FIELDS:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(RuntimeFieldError(field=field, code="type", message="Expected list of strings"))
                continue
            cleaned = _normalize_list([item.strip().lower() if field == "variants" else item.strip() for item in value])
            if field == "variants" and not cleaned:
                errors.append(RuntimeFieldError(field=field, code="min_items", message="At least one variant is required"))
                continue
            normalized[field] = cleaned
            continue

        if field in _RUNTIME_STR_FIELDS:
            if value is not None and not isinstance(value, str):
                errors.append(RuntimeFieldError(field=field, code="type", message="Expected string"))
                continue
            normalized[field] = value
            continue

        if field in _RUNTIME_BOOL_FIELDS:
            if value is not None and not isinstance(value, bool):
                errors.append(RuntimeFieldError(field=field, code="type", message="Expected boolean"))
                continue
            normalized[field] = value
            continue

        if field in _RUNTIME_INT_FIELDS:
            if value is None or not isinstance(value, int):
                errors.append(RuntimeFieldError(field=field, code="type", message="Expected integer"))
                continue
            lower, upper = _RUNTIME_INT_FIELDS[field]
            if value < lower or (upper is not None and value > upper):
                bounds = f">={lower}" if upper is None else f"between {lower} and {upper}"
                errors.append(RuntimeFieldError(field=field, code="range", message=f"Must be {bounds}"))
                continue
            normalized[field] = value

    return normalized, errors


def load_runtime_settings(settings_ini_path: Path) -> dict[str, Any]:
    config = configparser.ConfigParser()
    if settings_ini_path.exists():
        config.read(settings_ini_path, encoding="utf-8")

    for section in ["PATHS", "ANALYSIS", "PLAYER", "FETCH"]:
        if section not in config:
            config[section] = {}

    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]
    fetch = config["FETCH"]

    player_name = (player.get("name") or player.get("player_name") or "").strip()
    chesscom_usernames = _parse_list(fetch.get("chesscom_usernames"))
    lichess_usernames = _parse_list(fetch.get("lichess_usernames"))
    player_names = _normalize_list(_parse_list(player.get("player_names")) + ([player_name] if player_name else []))

    return {
        "chesscom_usernames": chesscom_usernames,
        "lichess_usernames": lichess_usernames,
        "variants": _parse_list(fetch.get("variants") or fetch.get("fetch_variants") or "blitz,rapid,daily"),
        "days_back": _safe_int(fetch.get("days_back") or fetch.get("fetch_days_back"), 180),
        "games_dir": paths.get("games_dir", ""),
        "database_path": paths.get("database_path", ""),
        "repertoire_dir": paths.get("repertoire_dir", ""),
        "stockfish_path": paths.get("stockfish_path", ""),
        "piece_dir": paths.get("piece_dir", ""),
        "engine_depth": _safe_int(analysis.get("engine_depth"), 20),
        "max_plies": _safe_int(analysis.get("max_plies"), 30),
        "player_name": player_name,
        "player_names": player_names,
        "rating_band_size": _safe_int(player.get("rating_band_size"), 100),
        "matching_mode": (analysis.get("matching_mode") or "STRICT").strip(),
        "enable_engine_cache": _safe_int(analysis.get("enable_engine_cache"), 1) > 0,
        "incremental_analysis": _safe_int(analysis.get("incremental_analysis"), 1) > 0,
        "review_top_n": _safe_int(analysis.get("review_top_n"), 25),
        "tabiya_top_n": _safe_int(analysis.get("tabiya_top_n"), 10),
        "engine_workers": _safe_int(analysis.get("engine_workers"), 0),
        "engine_worker_cap": _safe_int(analysis.get("engine_worker_cap"), 4),
        "engine_threads": _safe_int(analysis.get("engine_threads"), 1),
        "engine_hash_mb": _safe_int(analysis.get("engine_hash_mb"), 0),
        "engine_mode": (analysis.get("engine_mode") or "adaptive").strip().lower(),
        "engine_max_time_ms": _safe_int(analysis.get("engine_max_time_ms"), 300),
        "engine_profile": (analysis.get("engine_profile") or "aggressive").strip().lower(),
        "engine_cache_prune_non_active": _safe_int(analysis.get("engine_cache_prune_non_active"), 1) > 0,
        "missing_coverage_proposal_threshold": _safe_int(analysis.get("missing_coverage_proposal_threshold"), 5),
    }


def update_runtime_settings(settings_ini_path: Path, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[RuntimeFieldError]]:
    normalized, errors = _validate_runtime_payload(payload)
    if errors:
        return None, errors

    config = configparser.ConfigParser()
    if settings_ini_path.exists():
        config.read(settings_ini_path, encoding="utf-8")
    for section in ["PATHS", "ANALYSIS", "PLAYER", "FETCH"]:
        if section not in config:
            config[section] = {}

    fetch = config["FETCH"]
    fetch["chesscom_usernames"] = ",".join(normalized["chesscom_usernames"])
    fetch["lichess_usernames"] = ",".join(normalized["lichess_usernames"])
    fetch["variants"] = ",".join(normalized["variants"])
    fetch["fetch_variants"] = ",".join(normalized["variants"])
    fetch["days_back"] = str(normalized["days_back"])
    fetch["fetch_days_back"] = str(normalized["days_back"])

    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]

    for field in ("repertoire_dir", "games_dir", "database_path", "stockfish_path", "piece_dir"):
        if field in normalized and normalized[field] is not None:
            paths[field] = normalized[field]

    for field in (
        "engine_depth",
        "max_plies",
        "review_top_n",
        "tabiya_top_n",
        "engine_workers",
        "engine_worker_cap",
        "engine_threads",
        "engine_hash_mb",
        "engine_max_time_ms",
        "missing_coverage_proposal_threshold",
    ):
        if field in normalized and normalized[field] is not None:
            analysis[field] = str(normalized[field])

    for field in ("matching_mode", "engine_mode", "engine_profile"):
        if field in normalized and normalized[field] is not None:
            analysis[field] = str(normalized[field])

    for field in ("enable_engine_cache", "incremental_analysis", "engine_cache_prune_non_active"):
        if field in normalized and normalized[field] is not None:
            analysis[field] = "1" if normalized[field] else "0"

    if "player_name" in normalized and normalized["player_name"] is not None:
        player["name"] = normalized["player_name"]
        player["player_name"] = normalized["player_name"]
    if "player_names" in normalized and normalized["player_names"] is not None:
        player["player_names"] = ",".join(_normalize_list(normalized["player_names"]))
    if "rating_band_size" in normalized and normalized["rating_band_size"] is not None:
        player["rating_band_size"] = str(normalized["rating_band_size"])

    with settings_ini_path.open("w", encoding="utf-8") as file:
        config.write(file)

    return load_runtime_settings(settings_ini_path), []
