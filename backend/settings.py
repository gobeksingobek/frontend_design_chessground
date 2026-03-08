from __future__ import annotations

from dataclasses import dataclass
import os


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


SETTINGS = BackendSettings()
