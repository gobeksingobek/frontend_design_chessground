from __future__ import annotations

import configparser
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6 import QtWidgets


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_RATING_BAND_SIZE = 100
DEFAULT_FETCH_VARIANTS = ("blitz", "rapid", "daily")


@dataclass
class AppConfig:
    """Desktop-client configuration.

    Analysis settings are populated from the workspace API after connection and
    are never persisted back to this local file.
    """

    backend_url: str
    api_token: str
    piece_dir: str
    repertoire_dir: str = ""
    games_dir: str = ""
    rating_band_size: int = DEFAULT_RATING_BAND_SIZE
    fetch_variants: list[str] | None = None

    def with_workspace_settings(self, payload: dict) -> "AppConfig":
        variants = payload.get("variants") or list(DEFAULT_FETCH_VARIANTS)
        return replace(
            self,
            rating_band_size=int(payload.get("rating_band_size") or DEFAULT_RATING_BAND_SIZE),
            fetch_variants=[str(value) for value in variants],
        )


def _ensure_config_sections(config: configparser.ConfigParser) -> None:
    if "CLIENT" not in config:
        config["CLIENT"] = {}
    if "PATHS" not in config:
        config["PATHS"] = {}


def read_config_file(settings_path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if settings_path.exists():
        config.read(settings_path, encoding="utf-8")
    return config


def load_app_config(config: configparser.ConfigParser) -> AppConfig:
    _ensure_config_sections(config)
    client = config["CLIENT"]
    paths = config["PATHS"]
    return AppConfig(
        backend_url=(client.get("backend_url") or DEFAULT_BACKEND_URL).rstrip("/"),
        api_token=(client.get("api_token") or "dev-token").strip(),
        piece_dir=(paths.get("piece_dir") or "").strip(),
        repertoire_dir=(paths.get("repertoire_dir") or "").strip(),
        games_dir=(paths.get("games_dir") or "").strip(),
        fetch_variants=list(DEFAULT_FETCH_VARIANTS),
    )


def _prompt_directory(title: str) -> str:
    return QtWidgets.QFileDialog.getExistingDirectory(None, title)


def ensure_config_values(config: configparser.ConfigParser, base_dir: Path) -> AppConfig:
    _ensure_config_sections(config)
    client = config["CLIENT"]
    paths = config["PATHS"]
    changed = False
    if not client.get("backend_url"):
        client["backend_url"] = DEFAULT_BACKEND_URL
        changed = True
    if not client.get("api_token"):
        client["api_token"] = "dev-token"
        changed = True
    piece_dir = (paths.get("piece_dir") or "").strip()
    if not piece_dir or not Path(piece_dir).exists():
        selected = _prompt_directory("Select piece images directory")
        if selected:
            paths["piece_dir"] = selected
            changed = True
    # These paths are upload conveniences only; the server never reads them.
    paths.setdefault("repertoire_dir", "")
    paths.setdefault("games_dir", "")
    if changed:
        settings_path = base_dir / "config" / "settings.ini"
        with settings_path.open("w", encoding="utf-8") as handle:
            config.write(handle)
    return load_app_config(config)


def validate_app_config(config: AppConfig) -> list[str]:
    errors: list[str] = []
    if not config.backend_url.startswith(("http://", "https://")):
        errors.append("Backend URL must start with http:// or https://.")
    if not config.api_token:
        errors.append("API token is empty.")
    if not config.piece_dir:
        errors.append("Piece directory is empty.")
    elif not Path(config.piece_dir).exists():
        errors.append("Piece directory does not exist.")
    return errors
