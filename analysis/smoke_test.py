from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import chess.pgn

from analysis import pipeline
from storage import database

SMOKE_REPERTOIRE_GAMES = 30
SMOKE_INPUT_GAMES = 10


def _collect_sample_pgn_games(src_root: Path, dst_file: Path, limit: int) -> int:
    count = 0
    pgn_files = sorted(list(src_root.rglob("*.pgn")) + list(src_root.rglob("*.PGN")))
    dst_file.parent.mkdir(parents=True, exist_ok=True)

    with dst_file.open("w", encoding="utf-8") as out:
        first = True
        for pgn_path in pgn_files:
            with pgn_path.open("r", encoding="utf-8", errors="ignore") as handle:
                while count < limit:
                    game = chess.pgn.read_game(handle)
                    if game is None:
                        break
                    if not first:
                        out.write("\n\n")
                    exporter = chess.pgn.StringExporter(
                        headers=True, variations=False, comments=True
                    )
                    out.write(game.accept(exporter).strip())
                    first = False
                    count += 1
            if count >= limit:
                break
    return count


def _table_count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def run_smoke_test(
    app_config,
    base_dir: Path,
    progress_cb: Callable[[dict], None] | None = None,
) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    smoke_root = base_dir / f"_smoke_test_{run_id}"
    rep_dst = smoke_root / "repertoire" / "sample_repertoire.pgn"
    games_dst = smoke_root / "games" / "sample_games.pgn"

    smoke_db = Path(app_config.database_path).parent / f"analysis_smoke_{run_id}.db"
    smoke_db.parent.mkdir(parents=True, exist_ok=True)
    if smoke_db.exists():
        smoke_db.unlink()

    rep_written = _collect_sample_pgn_games(
        Path(app_config.repertoire_dir), rep_dst, SMOKE_REPERTOIRE_GAMES
    )
    games_written = _collect_sample_pgn_games(
        Path(app_config.games_dir), games_dst, SMOKE_INPUT_GAMES
    )

    smoke_cfg = replace(
        app_config,
        repertoire_dir=str(rep_dst.parent),
        games_dir=str(games_dst.parent),
        database_path=str(smoke_db),
        incremental_analysis=False,
    )

    def wrapped_progress(payload: dict) -> None:
        if not progress_cb:
            return
        tagged = dict(payload)
        phase = tagged.get("phase")
        tagged["phase"] = f"Smoke: {phase}" if phase else "Smoke"
        progress_cb(tagged)

    conn = database.ensure_db(str(smoke_db), reset_on_mismatch=True)
    try:
        pipeline.run_analysis(conn, smoke_cfg, reset_db=True, progress_cb=wrapped_progress)
        summary = {
            "smoke_root": str(smoke_root),
            "smoke_db": str(smoke_db),
            "repertoire_games_sampled": rep_written,
            "input_games_sampled": games_written,
            "repertoire_lines": _table_count(conn, "repertoire_lines"),
            "games": _table_count(conn, "games"),
            "matches": _table_count(conn, "matches"),
            "engine_cache": _table_count(conn, "engine_cache"),
            "analysis_ply": _table_count(conn, "analysis_ply"),
            "review_items": _table_count(conn, "review_items"),
            "insights": _table_count(conn, "insights"),
            "db_size_mb": round(smoke_db.stat().st_size / 1024 / 1024, 2),
        }
        return summary
    finally:
        conn.close()
