# Desktop capability inventory

## Source references
- `README.md`
- `main.py`
- `storage/queries.py`
- `storage/database.py`

## Capabilities from desktop app
- Loads and persists configuration from `config/settings.ini` (paths, player names, analysis and fetch settings).
- Imports repertoire PGNs and game PGNs, then runs matching/compliance analysis.
- Runs Stockfish engine analysis and stores per-ply eval metrics.
- Computes and stores aggregated statistics (lines, time usage, rating bands, insights).
- Supports tree exploration backed by repertoire edges and game transition stats.
- Supports trainer state management (`learned`, `needs_review`, streaks, priority overrides, auto-priority).
- Supports review propositions and branch queue decisions for missing-coverage branches.

## Storage paths and files
- Default SQLite DB: `data/analysis.db`.
- Runtime settings: `config/settings.ini`.
- Fetch state marker: `<games_dir>/.fetch_state.json` (analysis runtime manager path).

## Trainer/review storage tables
- `trainer_line_state`: learned/review progression and priority controls.
- `review_items`: generated review items shown in review view.
- `review_propositions`: actionable missing-coverage propositions.
- `branch_queue`: queue table for approved review propositions.
- `sideline_queue`: sideline requests from gameplay/deviation handling.
