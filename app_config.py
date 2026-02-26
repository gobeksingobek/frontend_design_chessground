from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtWidgets

DEFAULT_ENGINE_DEPTH = 20
DEFAULT_MAX_PLIES = 30
DEFAULT_RATING_BAND_SIZE = 100
DEFAULT_MATCHING_MODE = "STRICT"
DEFAULT_ENABLE_ENGINE_CACHE = 1
DEFAULT_INCREMENTAL_ANALYSIS = 1
DEFAULT_REVIEW_TOP_N = 25
DEFAULT_TABIYA_TOP_N = 10
DEFAULT_ENGINE_WORKERS = 0
DEFAULT_ENGINE_WORKER_CAP = 4
DEFAULT_ENGINE_THREADS = 1
DEFAULT_ENGINE_HASH_MB = 0
DEFAULT_ENGINE_MODE = "adaptive"
DEFAULT_ENGINE_MAX_TIME_MS = 300
DEFAULT_ENGINE_PROFILE = "aggressive"
DEFAULT_ENGINE_CACHE_PRUNE_NON_ACTIVE = 1
DEFAULT_MISSING_COVERAGE_PROPOSAL_THRESHOLD = 5
DEFAULT_FETCH_VARIANTS = "blitz,rapid,daily"
DEFAULT_FETCH_DAYS_BACK = 180
ALLOWED_FETCH_VARIANTS = {"blitz", "rapid", "daily"}


@dataclass
class AppConfig:
    repertoire_dir: str
    games_dir: str
    database_path: str
    stockfish_path: str
    piece_dir: str
    engine_depth: int
    max_plies: int
    player_name: str
    player_names: list[str]
    rating_band_size: int
    matching_mode: str
    enable_engine_cache: bool
    incremental_analysis: bool
    review_top_n: int
    tabiya_top_n: int
    engine_workers: int
    engine_worker_cap: int
    engine_threads: int
    engine_hash_mb: int
    engine_mode: str
    engine_max_time_ms: int
    engine_profile: str
    engine_cache_prune_non_active: bool
    missing_coverage_proposal_threshold: int
    chesscom_usernames: list[str]
    lichess_usernames: list[str]
    fetch_variants: list[str]
    fetch_days_back: int


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


def _sanitize_fetch_variants(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = (value or "").strip().lower()
        if key not in ALLOWED_FETCH_VARIANTS:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _ensure_config_sections(config: configparser.ConfigParser) -> None:
    for section in ["PATHS", "ANALYSIS", "PLAYER", "FETCH"]:
        if section not in config:
            config[section] = {}


def read_config_file(settings_path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if settings_path.exists():
        with settings_path.open("r", encoding="utf-8") as handle:
            config.read_file(handle)
    else:
        config.read(settings_path)
    return config


def load_app_config(config: configparser.ConfigParser) -> AppConfig:
    _ensure_config_sections(config)
    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]
    fetch = config["FETCH"]

    player_name = (player.get("name") or "").strip()
    fetch = config["FETCH"]
    chesscom_usernames = _parse_list(fetch.get("chesscom_usernames"))
    lichess_usernames = _parse_list(fetch.get("lichess_usernames"))
    combined_names: list[str] = []
    seen = set()
    for name in _parse_list(player_name) + chesscom_usernames + lichess_usernames:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        combined_names.append(name)
    return AppConfig(
        repertoire_dir=paths.get("repertoire_dir", ""),
        games_dir=paths.get("games_dir", ""),
        database_path=paths.get("database_path", ""),
        stockfish_path=paths.get("stockfish_path", ""),
        piece_dir=paths.get("piece_dir", ""),
        engine_depth=_safe_int(analysis.get("engine_depth"), DEFAULT_ENGINE_DEPTH),
        max_plies=_safe_int(analysis.get("max_plies"), DEFAULT_MAX_PLIES),
        player_name=player_name,
        player_names=combined_names,
        rating_band_size=_safe_int(
            player.get("rating_band_size"), DEFAULT_RATING_BAND_SIZE
        ),
        matching_mode=(analysis.get("matching_mode") or DEFAULT_MATCHING_MODE).strip(),
        enable_engine_cache=_safe_int(
            analysis.get("enable_engine_cache"), DEFAULT_ENABLE_ENGINE_CACHE
        )
        > 0,
        incremental_analysis=_safe_int(
            analysis.get("incremental_analysis"), DEFAULT_INCREMENTAL_ANALYSIS
        )
        > 0,
        review_top_n=_safe_int(analysis.get("review_top_n"), DEFAULT_REVIEW_TOP_N),
        tabiya_top_n=_safe_int(analysis.get("tabiya_top_n"), DEFAULT_TABIYA_TOP_N),
        engine_workers=_safe_int(analysis.get("engine_workers"), DEFAULT_ENGINE_WORKERS),
        engine_worker_cap=_safe_int(
            analysis.get("engine_worker_cap"), DEFAULT_ENGINE_WORKER_CAP
        ),
        engine_threads=_safe_int(analysis.get("engine_threads"), DEFAULT_ENGINE_THREADS),
        engine_hash_mb=_safe_int(analysis.get("engine_hash_mb"), DEFAULT_ENGINE_HASH_MB),
        engine_mode=(analysis.get("engine_mode") or DEFAULT_ENGINE_MODE).strip().lower(),
        engine_max_time_ms=_safe_int(
            analysis.get("engine_max_time_ms"), DEFAULT_ENGINE_MAX_TIME_MS
        ),
        engine_profile=(analysis.get("engine_profile") or DEFAULT_ENGINE_PROFILE)
        .strip()
        .lower(),
        engine_cache_prune_non_active=_safe_int(
            analysis.get("engine_cache_prune_non_active"),
            DEFAULT_ENGINE_CACHE_PRUNE_NON_ACTIVE,
        )
        > 0,
        missing_coverage_proposal_threshold=_safe_int(
            analysis.get("missing_coverage_proposal_threshold"),
            DEFAULT_MISSING_COVERAGE_PROPOSAL_THRESHOLD,
        ),
        chesscom_usernames=chesscom_usernames,
        lichess_usernames=lichess_usernames,
        fetch_variants=_sanitize_fetch_variants(
            _parse_list(fetch.get("fetch_variants") or DEFAULT_FETCH_VARIANTS)
        ),
        fetch_days_back=_safe_int(fetch.get("fetch_days_back"), DEFAULT_FETCH_DAYS_BACK),
    )


def _prompt_directory(title: str) -> str:
    directory = QtWidgets.QFileDialog.getExistingDirectory(None, title)
    if not directory:
        raise RuntimeError(f"{title} is required.")
    return directory


def _prompt_file(title: str) -> str:
    path, _ = QtWidgets.QFileDialog.getOpenFileName(None, title)
    if not path:
        raise RuntimeError(f"{title} is required.")
    return path


def _prompt_text(title: str, label: str) -> str:
    value, ok = QtWidgets.QInputDialog.getText(None, title, label)
    if not ok or not value:
        raise RuntimeError(f"{label} is required.")
    return value


def _save_config(config: configparser.ConfigParser, settings_path: Path) -> None:
    with settings_path.open("w", encoding="utf-8") as handle:
        config.write(handle)


def ensure_config_values(config: configparser.ConfigParser, base_dir: Path) -> AppConfig:
    _ensure_config_sections(config)
    paths = config["PATHS"]
    analysis = config["ANALYSIS"]
    player = config["PLAYER"]
    fetch = config["FETCH"]
    changed = False

    repertoire_dir = (paths.get("repertoire_dir") or "").strip()
    if not repertoire_dir or not Path(repertoire_dir).exists():
        repertoire_dir = _prompt_directory("Select repertoire PGN directory")
        paths["repertoire_dir"] = repertoire_dir
        changed = True

    games_dir = (paths.get("games_dir") or "").strip()
    if not games_dir or not Path(games_dir).exists():
        games_dir = _prompt_directory("Select Chess.com PGN directory")
        paths["games_dir"] = games_dir
        changed = True

    database_path = (paths.get("database_path") or "").strip()
    if not database_path:
        database_path = str(base_dir / "data" / "analysis.db")
        paths["database_path"] = database_path
        changed = True
    db_parent = Path(database_path).parent
    db_parent.mkdir(parents=True, exist_ok=True)

    stockfish_path = (paths.get("stockfish_path") or "").strip()
    if not stockfish_path or not Path(stockfish_path).exists():
        stockfish_path = _prompt_file("Select Stockfish executable")
        paths["stockfish_path"] = stockfish_path
        changed = True

    piece_dir = (paths.get("piece_dir") or "").strip()
    if not piece_dir or not Path(piece_dir).exists():
        piece_dir = _prompt_directory("Select piece images directory")
        paths["piece_dir"] = piece_dir
        changed = True

    player_name = (player.get("name") or "").strip()
    fetch_usernames = _parse_list(fetch.get("chesscom_usernames")) + _parse_list(
        fetch.get("lichess_usernames")
    )
    if not player_name and not fetch_usernames:
        player_name = _prompt_text("Player Name(s)", "Enter your Chess.com name(s)")
        player["name"] = player_name
        changed = True

    if "engine_depth" not in analysis or not analysis.get("engine_depth"):
        analysis["engine_depth"] = str(DEFAULT_ENGINE_DEPTH)
        changed = True
    if "max_plies" not in analysis or not analysis.get("max_plies"):
        analysis["max_plies"] = str(DEFAULT_MAX_PLIES)
        changed = True
    if "matching_mode" not in analysis or not analysis.get("matching_mode"):
        analysis["matching_mode"] = DEFAULT_MATCHING_MODE
        changed = True
    if "enable_engine_cache" not in analysis or not analysis.get("enable_engine_cache"):
        analysis["enable_engine_cache"] = str(DEFAULT_ENABLE_ENGINE_CACHE)
        changed = True
    if "incremental_analysis" not in analysis or not analysis.get("incremental_analysis"):
        analysis["incremental_analysis"] = str(DEFAULT_INCREMENTAL_ANALYSIS)
        changed = True
    if "engine_workers" not in analysis or not analysis.get("engine_workers"):
        analysis["engine_workers"] = str(DEFAULT_ENGINE_WORKERS)
        changed = True
    if "engine_worker_cap" not in analysis or not analysis.get("engine_worker_cap"):
        analysis["engine_worker_cap"] = str(DEFAULT_ENGINE_WORKER_CAP)
        changed = True
    if "engine_threads" not in analysis or not analysis.get("engine_threads"):
        analysis["engine_threads"] = str(DEFAULT_ENGINE_THREADS)
        changed = True
    if "engine_hash_mb" not in analysis or not analysis.get("engine_hash_mb"):
        analysis["engine_hash_mb"] = str(DEFAULT_ENGINE_HASH_MB)
        changed = True
    if "engine_mode" not in analysis or not analysis.get("engine_mode"):
        analysis["engine_mode"] = DEFAULT_ENGINE_MODE
        changed = True
    if "engine_max_time_ms" not in analysis or not analysis.get("engine_max_time_ms"):
        analysis["engine_max_time_ms"] = str(DEFAULT_ENGINE_MAX_TIME_MS)
        changed = True
    if "engine_profile" not in analysis or not analysis.get("engine_profile"):
        analysis["engine_profile"] = DEFAULT_ENGINE_PROFILE
        changed = True
    if (
        "engine_cache_prune_non_active" not in analysis
        or not analysis.get("engine_cache_prune_non_active")
    ):
        analysis["engine_cache_prune_non_active"] = str(
            DEFAULT_ENGINE_CACHE_PRUNE_NON_ACTIVE
        )
        changed = True
    if "review_top_n" not in analysis or not analysis.get("review_top_n"):
        analysis["review_top_n"] = str(DEFAULT_REVIEW_TOP_N)
        changed = True
    if "tabiya_top_n" not in analysis or not analysis.get("tabiya_top_n"):
        analysis["tabiya_top_n"] = str(DEFAULT_TABIYA_TOP_N)
        changed = True
    if (
        "missing_coverage_proposal_threshold" not in analysis
        or not analysis.get("missing_coverage_proposal_threshold")
    ):
        analysis["missing_coverage_proposal_threshold"] = str(
            DEFAULT_MISSING_COVERAGE_PROPOSAL_THRESHOLD
        )
        changed = True
    if "chesscom_usernames" not in fetch:
        fetch["chesscom_usernames"] = ""
        changed = True
    if "lichess_usernames" not in fetch:
        fetch["lichess_usernames"] = ""
        changed = True
    if "fetch_variants" not in fetch or not fetch.get("fetch_variants"):
        fetch["fetch_variants"] = DEFAULT_FETCH_VARIANTS
        changed = True
    if "fetch_days_back" not in fetch or not fetch.get("fetch_days_back"):
        fetch["fetch_days_back"] = str(DEFAULT_FETCH_DAYS_BACK)
        changed = True

    rating_band_size = _safe_int(player.get("rating_band_size"), DEFAULT_RATING_BAND_SIZE)
    if rating_band_size <= 0:
        rating_band_size = DEFAULT_RATING_BAND_SIZE
        player["rating_band_size"] = str(rating_band_size)
        changed = True
    elif "rating_band_size" not in player:
        player["rating_band_size"] = str(rating_band_size)
        changed = True

    if changed:
        settings_path = base_dir / "config" / "settings.ini"
        _save_config(config, settings_path)

    return load_app_config(config)


def validate_app_config(app_config: AppConfig) -> list[str]:
    errors: list[str] = []

    if not app_config.repertoire_dir:
        errors.append("Repertoire directory is empty.")
    elif not Path(app_config.repertoire_dir).exists():
        errors.append("Repertoire directory does not exist.")

    if not app_config.games_dir:
        errors.append("Games directory is empty.")
    elif not Path(app_config.games_dir).exists():
        errors.append("Games directory does not exist.")

    if not app_config.database_path:
        errors.append("Database path is empty.")

    if not app_config.stockfish_path:
        errors.append("Stockfish path is empty.")
    elif not Path(app_config.stockfish_path).exists():
        errors.append("Stockfish path does not exist.")

    if not app_config.piece_dir:
        errors.append("Piece directory is empty.")
    elif not Path(app_config.piece_dir).exists():
        errors.append("Piece directory does not exist.")

    if not app_config.player_names:
        errors.append("Player name list is empty.")

    if app_config.engine_depth <= 0:
        errors.append("Engine depth must be greater than 0.")

    if app_config.max_plies <= 0:
        errors.append("Max plies must be greater than 0.")

    if app_config.rating_band_size <= 0:
        errors.append("Rating band size must be greater than 0.")

    if app_config.matching_mode not in {"STRICT", "TRANSPOSITION"}:
        errors.append("Matching mode must be STRICT or TRANSPOSITION.")

    if app_config.review_top_n <= 0:
        errors.append("Review top N must be greater than 0.")

    if app_config.tabiya_top_n <= 0:
        errors.append("Tabiya top N must be greater than 0.")

    if app_config.engine_workers < 0:
        errors.append("Engine workers must be 0 or greater.")

    if app_config.engine_worker_cap < 1:
        errors.append("Engine worker cap must be at least 1.")

    if app_config.engine_threads < 0:
        errors.append("Engine threads must be 0 or greater.")

    if app_config.engine_hash_mb < 0:
        errors.append("Engine hash MB must be 0 or greater.")
    if app_config.engine_mode not in {"adaptive", "fixed"}:
        errors.append("Engine mode must be adaptive or fixed.")
    if app_config.engine_max_time_ms <= 0:
        errors.append("Engine max time must be greater than 0 milliseconds.")
    if app_config.engine_profile not in {
        "aggressive",
        "balanced",
        "conservative",
        "manual",
    }:
        errors.append(
            "Engine profile must be aggressive, balanced, conservative, or manual."
        )
    if app_config.fetch_days_back <= 0:
        errors.append("Fetch days back must be greater than 0.")
    if app_config.missing_coverage_proposal_threshold < 1:
        errors.append("Missing coverage proposal threshold must be at least 1.")

    return errors
