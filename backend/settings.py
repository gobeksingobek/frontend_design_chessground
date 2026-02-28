from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BackendSettings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/chessground")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    api_auth_token: str = os.getenv("API_AUTH_TOKEN", "dev-token")
    stream_name: str = os.getenv("SIDELINE_STREAM_NAME", "sideline:jobs")
    dead_letter_stream: str = os.getenv("SIDELINE_DEAD_LETTER_STREAM", "sideline:jobs:dead")
    consumer_group: str = os.getenv("SIDELINE_CONSUMER_GROUP", "sideline-workers")
    consumer_name: str = os.getenv("SIDELINE_CONSUMER_NAME", "worker-1")
    max_retries: int = int(os.getenv("SIDELINE_MAX_RETRIES", "3"))
    stream_block_ms: int = int(os.getenv("SIDELINE_STREAM_BLOCK_MS", "5000"))
    stockfish_path: str = os.getenv("STOCKFISH_PATH", "stockfish")
    stockfish_depth: int = int(os.getenv("STOCKFISH_DEPTH", "14"))


SETTINGS = BackendSettings()
