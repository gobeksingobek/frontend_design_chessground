from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import chess.pgn

try:
    from storage import queries
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from repertoire_analyzer.storage import queries


USER_AGENT = "RepertoireAnalyzer/1.0"
CHESSCOM_ARCHIVES_URL = "https://api.chess.com/pub/player/{username}/games/archives"
LICHESS_EXPORT_URL = "https://lichess.org/api/games/user/{username}"
ALLOWED_FETCH_VARIANTS = {"blitz", "rapid", "daily"}


@dataclass
class FetchSummary:
    source: str
    username: str
    fetched_files: int = 0
    skipped_files: int = 0
    games_seen: int = 0
    games_written: int = 0
    games_skipped_in_db: int = 0
    message: str = ""


def _http_get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8", errors="replace"))


def _http_get_stream(url: str, headers: dict[str, str] | None = None):
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    return urlopen(req, timeout=60)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _dt_to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _month_end(year: int, month: int) -> datetime:
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return next_month - timedelta(seconds=1)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _parse_archive_month(url: str) -> tuple[int, int] | None:
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) < 2:
        return None
    try:
        year = int(parts[-2])
        month = int(parts[-1])
        return year, month
    except ValueError:
        return None


def _variant_set(variants: Iterable[str]) -> set[str]:
    return {
        v.strip().lower()
        for v in variants
        if v.strip() and v.strip().lower() in ALLOWED_FETCH_VARIANTS
    }


def _append_message(summary: FetchSummary, text: str) -> None:
    if not text:
        return
    if summary.message:
        summary.message = f"{summary.message}; {text}"
    else:
        summary.message = text


def _split_pgn_games(pgn_blob: str) -> list[str]:
    blob = pgn_blob.strip()
    if not blob:
        return []
    chunks = re.split(r"\r?\n\r?\n(?=\[Event )", blob)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _compute_hash_from_pgn(pgn_text: str) -> str | None:
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return None
    if game is None:
        return None
    tags = dict(game.headers)
    moves_uci = [move.uci() for move in game.mainline_moves()]
    return queries.compute_game_hash(tags, moves_uci)


def _filter_new_games(
    pgn_chunks: list[str],
    existing_pgn_hashes: set[str],
    summary: FetchSummary,
) -> list[str]:
    new_chunks: list[str] = []
    parse_failures = 0
    for pgn_chunk in pgn_chunks:
        pgn_hash = _compute_hash_from_pgn(pgn_chunk)
        if not pgn_hash:
            parse_failures += 1
            continue
        summary.games_seen += 1
        if pgn_hash in existing_pgn_hashes:
            summary.games_skipped_in_db += 1
            continue
        existing_pgn_hashes.add(pgn_hash)
        new_chunks.append(pgn_chunk)
    if parse_failures:
        _append_message(summary, f"parse skipped {parse_failures}")
    return new_chunks


def fetch_games(
    *,
    games_dir: Path,
    chesscom_usernames: list[str],
    lichess_usernames: list[str],
    variants: list[str],
    days_back: int,
    state_path: Path,
    existing_pgn_hashes: set[str] | None = None,
) -> list[FetchSummary]:
    summaries: list[FetchSummary] = []
    variants_set = _variant_set(variants)
    if not variants_set:
        return [FetchSummary(source="all", username="all", message="No variants selected.")]

    now = datetime.now(timezone.utc)
    since_floor = now - timedelta(days=days_back)
    state = _load_state(state_path)
    known_hashes = set(existing_pgn_hashes or set())

    chesscom_root = games_dir / "chesscom"
    lichess_root = games_dir / "lichess"
    chesscom_root.mkdir(parents=True, exist_ok=True)
    lichess_root.mkdir(parents=True, exist_ok=True)

    for username in chesscom_usernames:
        summaries.append(
            _fetch_chesscom_user(
                username=username,
                output_dir=chesscom_root,
                variants=variants_set,
                since_floor=since_floor,
                now=now,
                state=state,
                existing_pgn_hashes=known_hashes,
            )
        )

    for username in lichess_usernames:
        summaries.append(
            _fetch_lichess_user(
                username=username,
                output_dir=lichess_root,
                variants=variants_set,
                since_floor=since_floor,
                now=now,
                state=state,
                existing_pgn_hashes=known_hashes,
            )
        )

    _save_state(state_path, state)
    return summaries


def _fetch_chesscom_user(
    *,
    username: str,
    output_dir: Path,
    variants: set[str],
    since_floor: datetime,
    now: datetime,
    state: dict,
    existing_pgn_hashes: set[str],
) -> FetchSummary:
    summary = FetchSummary(source="chesscom", username=username)
    try:
        data = _http_get_json(CHESSCOM_ARCHIVES_URL.format(username=username))
    except HTTPError as exc:
        if exc.code == 404:
            summary.message = "Username not found (404). Check Chess.com username."
            return summary
        summary.message = f"Fetch failed: {exc}"
        return summary
    except (URLError, json.JSONDecodeError) as exc:
        summary.message = f"Fetch failed: {exc}"
        return summary

    archives = data.get("archives") or []
    for archive_url in archives:
        parsed = _parse_archive_month(archive_url)
        if not parsed:
            continue
        year, month = parsed
        month_start = _month_start(year, month)
        month_end = _month_end(year, month)
        if month_end < since_floor or month_start > now:
            continue

        file_name = f"{username}_{year:04d}-{month:02d}.pgn"
        out_path = output_dir / file_name

        try:
            # Use the archive URL returned by Chess.com to avoid format mismatches.
            month_data = _http_get_json(archive_url)
        except HTTPError as exc:
            if exc.code == 404:
                continue
            summary.message = f"Fetch failed: {exc}"
            return summary
        except (URLError, json.JSONDecodeError) as exc:
            summary.message = f"Fetch failed: {exc}"
            return summary

        games = month_data.get("games") or []
        pgn_chunks: list[str] = []
        for game in games:
            time_class = (game.get("time_class") or "").lower()
            if time_class not in variants:
                continue
            pgn = game.get("pgn")
            if pgn:
                pgn_chunks.append(pgn.strip())

        new_chunks = _filter_new_games(pgn_chunks, existing_pgn_hashes, summary)
        if new_chunks:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.exists() and out_path.stat().st_size > 0:
                with out_path.open("a", encoding="utf-8") as handle:
                    handle.write("\n\n")
                    handle.write("\n\n".join(new_chunks))
                    handle.write("\n")
            else:
                out_path.write_text("\n\n".join(new_chunks) + "\n", encoding="utf-8")
            summary.fetched_files += 1
            summary.games_written += len(new_chunks)
        else:
            summary.skipped_files += 1

    state_key = f"chesscom:{username}"
    state[state_key] = {"last_fetch": _dt_to_iso(now)}
    return summary


def _fetch_lichess_user(
    *,
    username: str,
    output_dir: Path,
    variants: set[str],
    since_floor: datetime,
    now: datetime,
    state: dict,
    existing_pgn_hashes: set[str],
) -> FetchSummary:
    summary = FetchSummary(source="lichess", username=username)

    state_key = f"lichess:{username}"
    last_fetch = _iso_to_dt(state.get(state_key, {}).get("last_fetch"))
    since = since_floor if not last_fetch else max(last_fetch, since_floor)
    if since >= now:
        summary.message = "Up to date."
        return summary

    perf_map = {
        "blitz": "blitz",
        "rapid": "rapid",
        "daily": "correspondence",
    }
    perf_types = [perf_map[v] for v in variants if v in perf_map]
    params = {
        "since": int(since.timestamp() * 1000),
        "until": int(now.timestamp() * 1000),
        "perfType": ",".join(perf_types),
        "max": 10000,
    }
    url = f"{LICHESS_EXPORT_URL.format(username=username)}?{urlencode(params)}"

    try:
        response = _http_get_stream(
            url, headers={"Accept": "application/x-chess-pgn"}
        )
    except HTTPError as exc:
        if exc.code == 429:
            summary.message = "Rate limited by Lichess. Try again later."
            return summary
        summary.message = f"Fetch failed: {exc}"
        return summary
    except URLError as exc:
        summary.message = f"Fetch failed: {exc}"
        return summary

    chunks: list[bytes] = []
    try:
        first_chunk = response.read(1024)
        if not first_chunk:
            summary.message = "No new games."
            state[state_key] = {"last_fetch": _dt_to_iso(now)}
            return summary
        chunks.append(first_chunk)
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        response.close()

    pgn_blob = b"".join(chunks).decode("utf-8", errors="replace")
    pgn_chunks = _split_pgn_games(pgn_blob)
    new_chunks = _filter_new_games(pgn_chunks, existing_pgn_hashes, summary)
    if not new_chunks:
        summary.skipped_files += 1
        if not summary.message:
            summary.message = "No new games."
        state[state_key] = {"last_fetch": _dt_to_iso(now)}
        return summary

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{username}_{timestamp}.pgn"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(new_chunks) + "\n", encoding="utf-8")

    summary.fetched_files += 1
    summary.games_written = len(new_chunks)
    state[state_key] = {"last_fetch": _dt_to_iso(now)}
    time.sleep(0.1)
    return summary
