from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
from uuid import UUID


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
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/chessground")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    workspace_id: str = os.getenv("WORKSPACE_ID", "00000000-0000-0000-0000-000000000001")
    api_auth_token: str = os.getenv("API_AUTH_TOKEN", "dev-token")
    api_cors_origins: tuple[str, ...] = _parse_csv(os.getenv("API_CORS_ORIGINS"))
    orchestration_stream: str = os.getenv("ORCHESTRATION_STREAM_NAME", "chessground:jobs:orchestration")
    engine_stream: str = os.getenv("ENGINE_STREAM_NAME", "chessground:jobs:engine")
    ingest_stream: str = os.getenv("INGEST_STREAM_NAME", "chessground:jobs:ingest")
    orchestration_consumer_group: str = os.getenv("ORCHESTRATION_CONSUMER_GROUP", "orchestrators")
    engine_consumer_group: str = os.getenv("ENGINE_CONSUMER_GROUP", "engine-workers")
    ingest_consumer_group: str = os.getenv("INGEST_CONSUMER_GROUP", "ingest-workers")
    worker_capability: str = os.getenv("WORKER_CAPABILITY", "engine").strip().lower()
    consumer_name: str = os.getenv("WORKER_CONSUMER_NAME", "worker-1")
    max_retries: int = int(os.getenv("JOB_MAX_RETRIES", "3"))
    stream_block_ms: int = int(os.getenv("JOB_STREAM_BLOCK_MS", "5000"))
    job_lease_seconds: int = int(os.getenv("JOB_LEASE_SECONDS", "120"))
    pending_claim_idle_ms: int = int(os.getenv("JOB_PENDING_CLAIM_IDLE_MS", "120000"))
    stockfish_path: str = os.getenv("STOCKFISH_PATH", "stockfish")
    stockfish_engine_id: str = os.getenv("STOCKFISH_ENGINE_ID", "stockfish")
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "14"))

    def validate_deployment_config(self, service: str = "api") -> None:
        try:
            UUID(self.workspace_id)
        except ValueError as exc:
            raise RuntimeError("WORKSPACE_ID must be a UUID.") from exc
        if self.worker_capability not in {"orchestration", "engine", "ingest"}:
            raise RuntimeError("WORKER_CAPABILITY must be orchestration, engine, or ingest.")
        if self.is_production_environment and service == "api":
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
        if self.is_production_environment and service in {"api", "orchestration", "engine"}:
            if not self.stockfish_engine_id.strip() or self.stockfish_engine_id == "stockfish":
                raise RuntimeError(
                    "STOCKFISH_ENGINE_ID must include the deployed engine name/version in production."
                )

    def stream_for(self, workload_class: str) -> str:
        return {
            "orchestration": self.orchestration_stream,
            "engine": self.engine_stream,
            "ingest": self.ingest_stream,
        }[workload_class]

    def dead_letter_stream_for(self, workload_class: str) -> str:
        return f"{self.stream_for(workload_class)}:dead"

    def consumer_group_for(self, workload_class: str) -> str:
        return {
            "orchestration": self.orchestration_consumer_group,
            "engine": self.engine_consumer_group,
            "ingest": self.ingest_consumer_group,
        }[workload_class]


SETTINGS = BackendSettings()


@dataclass(frozen=True)
class RuntimeFieldError:
    field: str
    code: str
    message: str


DEFAULT_RUNTIME_SETTINGS: dict[str, Any] = {
    "chesscom_usernames": [],
    "lichess_usernames": [],
    "variants": ["blitz", "rapid", "daily"],
    "days_back": 180,
    "player_name": "",
    "player_names": [],
    "engine_depth": 20,
    "max_plies": 30,
    "rating_band_size": 100,
    "matching_mode": "STRICT",
    "enable_engine_cache": True,
    "incremental_analysis": True,
    "review_top_n": 25,
    "tabiya_top_n": 10,
    "missing_coverage_proposal_threshold": 5,
}

_LIST_FIELDS = {"chesscom_usernames", "lichess_usernames", "variants", "player_names"}
_STRING_FIELDS = {"player_name", "matching_mode"}
_BOOLEAN_FIELDS = {"enable_engine_cache", "incremental_analysis"}
_INTEGER_FIELDS: dict[str, tuple[int, int | None]] = {
    "days_back": (1, 3650),
    "engine_depth": (1, None),
    "max_plies": (1, None),
    "rating_band_size": (1, None),
    "review_top_n": (1, None),
    "tabiya_top_n": (1, None),
    "missing_coverage_proposal_threshold": (1, None),
}
_ALLOWED_FIELDS = _LIST_FIELDS | _STRING_FIELDS | _BOOLEAN_FIELDS | set(_INTEGER_FIELDS)


def _deduplicate_strings(values: list[str], *, lowercase: bool = False) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip().lower() if lowercase else value.strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            output.append(cleaned)
    return output


def merge_runtime_settings_payload(
    current: dict[str, Any], payload: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[RuntimeFieldError]]:
    errors: list[RuntimeFieldError] = []
    unknown = sorted(set(payload) - _ALLOWED_FIELDS)
    errors.extend(RuntimeFieldError(field, "unknown_field", "Unknown field") for field in unknown)
    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        if field in _LIST_FIELDS:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(RuntimeFieldError(field, "type", "Expected list of strings"))
                continue
            cleaned = _deduplicate_strings(value, lowercase=field == "variants")
            if field == "variants" and (not cleaned or set(cleaned) - {"bullet", "blitz", "rapid", "daily"}):
                errors.append(RuntimeFieldError(field, "unsupported_variant", "Allowed: bullet, blitz, rapid, daily"))
                continue
            normalized[field] = cleaned
        elif field in _STRING_FIELDS:
            if not isinstance(value, str):
                errors.append(RuntimeFieldError(field, "type", "Expected string"))
            elif field == "matching_mode" and value.strip().upper() not in {"STRICT", "TRANSPOSITION"}:
                errors.append(RuntimeFieldError(field, "unsupported_mode", "Allowed: STRICT, TRANSPOSITION"))
            else:
                normalized[field] = value.strip().upper() if field == "matching_mode" else value.strip()
        elif field in _BOOLEAN_FIELDS:
            if not isinstance(value, bool):
                errors.append(RuntimeFieldError(field, "type", "Expected boolean"))
            else:
                normalized[field] = value
        elif field in _INTEGER_FIELDS:
            if not isinstance(value, int):
                errors.append(RuntimeFieldError(field, "type", "Expected integer"))
                continue
            lower, upper = _INTEGER_FIELDS[field]
            if value < lower or (upper is not None and value > upper):
                errors.append(RuntimeFieldError(field, "range", f"Must be at least {lower}"))
            else:
                normalized[field] = value
    if errors:
        return None, errors
    merged = {**DEFAULT_RUNTIME_SETTINGS, **current, **normalized}
    return merged, []
