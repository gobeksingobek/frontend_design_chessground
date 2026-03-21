# Repertoire Analyzer

## Overview

This project analyzes your Chess.com games against your memorized repertoire and stores results in PostgreSQL. The current desktop app reads from the database for presentation, while parsing and analysis are primarily handled in the backend pipeline.

## Guidance for coding agents and contributors

This repository includes workflow and parity docs intended to **guide implementation** and make release decisions auditable. Unless a task explicitly says otherwise, treat the following as **release-time guidance**, not as hard blockers for every code change:

- `docs/web_desktop_parity_checklist.md`
- `docs/release_cutover_checklist.md`
- `suggestions.txt`

For implementation tasks, prefer the smallest change that solves the user request cleanly. Use the parity and cutover docs to understand longer-term direction, testing expectations, and release readiness.

## Architecture notes

### Current architecture

These points describe how the project works today:

- The desktop app loads runtime settings from `config/settings.ini`.
- Repertoire and game PGNs are parsed by the analysis pipeline.
- Parsed data, matches, and derived analysis are stored in PostgreSQL.
- The desktop GUI and web surfaces primarily read precomputed data rather than recomputing heavy analysis inline.
- Server deployments can use the backend services in `backend/` for API and worker processes.

### Hard invariants

These are the behaviors to preserve unless a task explicitly asks to change them:

- PostgreSQL is the source of truth for persisted analysis data.
- Runtime features that depend on stored analysis should continue to work from persisted data, not only transient in-memory state.
- Repertoire import through the current web/API path accepts `.zip` archives containing PGNs or single `.pgn` files; `.db` and `.sql` snapshots are not accepted there.
- Redis Streams are used as transient queue transport for sideline/background job workflows; request state and results belong in Postgres.

### Preferred but changeable behavior

These are current defaults or architectural preferences. They are useful guidance, but they may be changed when a task benefits from doing so safely:

- Keep heavy computation in the analysis/backend path instead of the UI when practical.
- Keep the GUI and web UI focused on reading and displaying persisted results.
- Preserve existing matching/compliance behavior unless a task explicitly extends or replaces it.
- Prefer incremental or additive schema and UI changes over disruptive rewrites.
- Use the parity docs to plan tests and release readiness, but do not treat them as mandatory completion gates for unrelated implementation tasks.

## Setup

1. Create and activate a virtual environment (optional).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

On first run, the app will prompt you to select:
- Repertoire PGN directory
- Chess.com PGN directory
- Stockfish executable
- Piece images directory
- Your Chess.com player name(s) (comma-separated if multiple)

These values are saved to `config/settings.ini`.

You can edit settings from the app via Settings -> Edit settings.ini. Changes apply immediately.

`config/settings.ini` includes `piece_dir` under the `[PATHS]` section to point at your PNG piece set.
`config/settings.ini` includes `rating_band_size` under the `[PLAYER]` section to control the default rating-band size.
Other analysis controls live under `[ANALYSIS]`, including `matching_mode`, `enable_engine_cache`, `incremental_analysis`, `review_top_n`, and `tabiya_top_n`.
Fetch settings live under `[FETCH]` with `chesscom_usernames`, `lichess_usernames`, `fetch_variants`, and `fetch_days_back`.

Key analysis options:
- `matching_mode`: `STRICT` (longest UCI prefix) or `TRANSPOSITION` (position prefix).
- `enable_engine_cache`: reuse cached evaluations for repeated positions under the active engine mode/depth profile.
- `incremental_analysis`: skip unchanged PGN files on Run Analysis.
- `engine_mode`: `adaptive` (depth + time cap) or `fixed` (depth only).
- `engine_max_time_ms`: per-position cap used by adaptive mode (default `300`).
- `engine_profile`: `aggressive`, `balanced`, `conservative`, or `manual` worker sizing.
- `engine_cache_prune_non_active`: keep only active engine mode/depth cache rows.

## How the script works (end-to-end)

1) Configuration
- The app loads `config/settings.ini`, prompts for missing paths/name, then saves updates back to the INI.
- The INI controls: input directories, database path, Stockfish path, engine depth, player name(s), rating band size, and analysis options. Use comma-separated names for multiple accounts.

2) Repertoire loading
- All PGN files under the repertoire directory are scanned.
- Each PGN game is treated as a separate repertoire line.
- The line ID is taken from the PGN [Event] tag and should remain unique and non-empty for predictable analysis results.
- Optional priority tag: `[RepertoirePriority "1"]` marks a line as priority (only value `1` is currently recognized).
- In the current strict model, the same position via a different move order is treated as a different line.

3) Game loading
- All PGN files under the Chess.com games directory are scanned.
- Only games where White or Black matches your player name(s) (case-insensitive) are kept.
- Moves are parsed in order, and clock comments like `[%clk 0:02:59.9]` are read.
- Time control like `600+5` is parsed; daily/correspondence games are excluded from time stats.
- Trainer auto-priority currently increases trainer priority scores for lines that appear in your games, and auto-marks mainline at your deviation if you stayed in book to at least ply 10.

4) Matching and compliance
- Each game is currently matched against the repertoire line with the longest UCI move-prefix match.
- Ties are used only at analysis time; tie line IDs are not persisted in the database.
- `matched_line_id` is currently stored only for `FULLY_COMPLIANT` games.
- The app tracks `max_matched_ply` plus the first opponent and self deviation ply.
- Compliance is labeled as: `FULLY_COMPLIANT`, `INCOMPLETE`, `OPPONENT_DEVIATED`, `YOU_DEVIATED`, or `BOTH_DEVIATED`.
- `FULLY_COMPLIANT` currently requires completing the matched line; short prefix-only games are labeled `INCOMPLETE`.
- Tags are added to matches (for example `TRANSPOSITION`, `NOVELTY`, `BLUNDER_LIKE`) when applicable.

5) Engine analysis
- Stockfish can run in `adaptive` mode (depth target with per-position time cap) or `fixed` depth mode.
- For each ply it stores evaluation, best move, and centipawn loss on your moves only.
- `max_plies` is ignored for engine analysis.

6) Time analysis
- For each move, time spent is computed from clock values and increment.
- Daily games are excluded from time-based stats.
- Time patterns are derived per game: slow in-book, instant out-of-book (first out-of-repertoire move within 10 plies), and blunder clusters (a 200+ CPL blunder within 6 plies after leaving book).

7) Storage
- All parsed data, matches, and analysis results are stored in PostgreSQL.
- The GUI currently reads from PostgreSQL and does not compute the full analysis pipeline directly.
- Insights and review items are stored in PostgreSQL and displayed in their tabs.
- Repertoire lines are stored in compact JSON form (`repertoire_compact`) and exposed through a compatibility `line_positions` view.

## Tabs and how to use them

### Overview
- Shows the active paths and a quick summary of lines, games, matches, and compliance.
- Summary shows both `Manual priority` (PGN-tagged lines) and `Auto-priority` (trainer lines prioritized from your games).
- Shows a `Last refresh` timestamp after tab data is reloaded.
- Use Run Analysis to populate or refresh the database after changing PGNs or settings.
- Use Run Engine Analysis to evaluate existing DB games, recompute trainer auto-priority from current matches, and refresh derived review/insights without re-importing or rematching games.
- Use Run Smoke Test to generate a small sampled repertoire/games dataset and run full analysis in a separate smoke DB.
- Analysis status shows live phase/progress/ETA during engine computation.
- Use Full reanalysis (overwrite DB) for a clean rebuild.
- Use Refresh to reload summary counters from PostgreSQL.
- Use Fetch Games to download the last 180 days of games for selected variants into:
  - `games_dir/chesscom/` for Chess.com
  - `games_dir/lichess/` for Lichess
  - Fetch is DB-aware: only games not already present in PostgreSQL are written.
  - Chess.com current-month archives are included; reruns append only newly found games.

### Games
- Per-game summary table with players, result, ratings, line ID (shown for fully compliant games), compliance, max matched ply, matching mode, who left first, and in/out-of-repertoire counts.
- Use this to inspect which line a game matched and how far it stayed in book.

### Game details
- Select a game to view a live board, eval bar, and per-move table with quality colors.
- Arrow keys: Right/Left to step moves, Up/Down to jump to end/start.
- The repertoire prompt shows the line up to your deviation and the expected move at that ply.
- Use Create sideline at deviation for `YOU_DEVIATED` games (currently a placeholder; persistence is coming next).
- Use Reanalyze game to rematch the game (no engine) after repertoire changes.

### Lines
- Aggregated stats per repertoire line ID.
- Includes compliance rate, average deviation ply, W/D/L, average eval at exit, in-repertoire-other rate, opponent deviation to known rate, and time in-book vs out-of-book.

### Time usage
- Monthly aggregation of time usage (in-book vs out-of-book) on your moves, plus normalized % usage.
- Daily/correspondence games are excluded from this tab.
- Pattern counters summarize slow in-book, instant out-of-book, and blunder-cluster flags.

### Rating bands
- Aggregated stats by rating bands for both White and Black.
- Adjust the band size with the spinner; it defaults to `rating_band_size` from the INI.
- Time usage includes both seconds and normalized percentages.

### Insights
- Aggregated conclusions derived from PostgreSQL (coverage, deviations, time patterns, and performance).

### Trainer
- Learn and Review your repertoire lines with a large interactive board.
- Learn mode: the app shows your moves first, you replay them, then you complete the line.
- Review mode: you play the line; wrong moves are flagged and prioritized for review.
- Use Mark Priority to set a trainer-only priority override (stored in PostgreSQL).

### Review
- Review items (line ID + reason + detail) currently include signals such as:
  - early self-deviation
  - repeated opponent deviation
  - poor performance (losses > wins)
  - early self-deviation with high CPL
  - missing coverage hotspots

## Typical workflow

1) Configure paths (first run) or open Settings -> Edit settings.ini.
2) Click Run Analysis on the Overview tab.
3) Review results across Games, Lines, Time usage, Rating bands, and Review.
4) After updating PGNs or settings, run analysis again.

## Repertoire upload format (web/API)

Repertoire import accepts either:
- a `.zip` archive containing one or more PGN files (`*.pgn` / `*.PGN`, nested folders allowed), or
- a single `.pgn` file.

Database snapshot uploads (`.db`, `.sql`) are not accepted by the current web/API import path.

Import safety checks include:
- payload-level idempotency (exact same upload bytes are rejected as already imported), and
- line-level deduplication using canonical repertoire path hashing (duplicate lines are skipped with a user-facing message).

## Async backend services (API + Worker)

For server deployments, use the backend processes in `backend/`:

- API (`backend.api_service:app`): FastAPI validation/auth + sideline request creation + queue enqueue + read APIs.
- Worker (`backend.worker_service`): Redis Stream consumer-group worker that runs Stockfish branch analysis with retry and dead-letter behavior.

Postgres remains the source of truth (request rows, statuses, results, idempotency), while Redis Streams are transient queue transport only.

See `backend/README.md` for run commands and environment variables.

Desktop/web parity tracking checklist:
- `docs/web_desktop_parity_checklist.md`

Render/Neon migration path:
- Deploy `web/` (Next.js), `backend.api_service`, and `backend.worker_service` as separate Render services.
- Configure Render env vars as follows:
  - Web: `NEXT_PUBLIC_API_BASE_URL` (API URL, not web URL), `NEXT_PUBLIC_API_TOKEN`
  - API: `POSTGRES_DSN`, `REDIS_URL`, `API_AUTH_TOKEN`, `API_CORS_ORIGINS`, `DATA_BACKEND=postgres`, `ENFORCE_POSTGRES_ON_RENDER=1`
  - Worker: `POSTGRES_DSN`, `REDIS_URL`, `STOCKFISH_PATH`
- Verify `NEXT_PUBLIC_API_TOKEN` and `API_AUTH_TOKEN` match (unless browser login flow intentionally overrides token usage).
- Redeploy web, API, and worker services after env var updates.
- Bootstrap Postgres schema before API startup:
  - `python -m backend.bootstrap_postgres_schema`
- A Render blueprint is included at `render.yaml`.

## PostgreSQL graph schema (optional)

A normalized PostgreSQL version of the repertoire graph schema is provided at:

- `storage/postgres/schema.sql`

It uses global edge-level deduplication (`edges` unique on `(pos_id, uci_move, next_pos_id)`), line composition via `line_membership`, per-user mainline selection via `user_mainline`, and optional `line_path_cache` with trigger-based invalidation.
