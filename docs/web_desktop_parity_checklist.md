# Desktop ↔ Web parity checklist

This checklist uses `docs/desktop_capabilities_inventory.md` as the source of truth and maps each desktop capability to concrete web surfaces.

## Capability-to-surface map (source-of-truth mapping)


## Wiring status (current)

- This document is **fully populated as a planning/checklist artifact** for all requested tabs.
- Product parity is **not fully wired in code yet**; most items remain `In progress` or `Open` and are intentionally tracked as implementation work.
- A baseline regression cluster is wired for game-details API behavior and keyboard navigation helper logic only.

| Desktop capability (inventory) | Web frontend route(s) + component(s) | Backend endpoint(s) | Parity state |
| --- | --- | --- | --- |
| Loads/persists runtime configuration (`config/settings.ini`) | `/settings` → `web/src/app/(app)/settings/page.tsx` | `GET /settings/runtime`, `PUT /settings/runtime` | **Partial** (fetch/save settings is present; desktop-equivalent setting breadth and validation messaging are still limited). |
| Imports repertoire/game PGNs and runs matching/compliance analysis | `/overview`, `/repertoires`, `/games` → `overview/page.tsx`, `repertoires/page.tsx`, `games/page.tsx` | `POST /repertoires/import`, `POST /analysis/run/full`, `POST /analysis/run/fetch-games`, `GET /games` | **Partial** (core triggers exist, but cross-tab workflow and completion affordances are not desktop-equivalent). |
| Runs Stockfish analysis and stores per-ply eval metrics | `/overview`, `/games/[id]`, `/analysis` → `overview/page.tsx`, `games/[id]/page.tsx`, `components/analysis/sideline-analysis-form.tsx` | `POST /analysis/run/engine-only`, `POST /analysis/run/full`, `GET /games/{game_id}`, `POST /sidelines` | **Partial** (runs exist, but desktop-style guided progression and feedback loops are incomplete). |
| Computes/stores aggregate stats (lines, time, rating, insights) | `/overview`, `/lines`, `/time-usage`, `/rating-bands`, `/insights`, `/review` | `GET /overview/summary`, `GET /lines/stats`, `GET /time-usage/stats`, `GET /rating-bands/stats`, `GET /insights`, `GET /review/items` | **Partial** (tables present; desktop drill-down and context-aware pivots are still missing). |
| Supports tree exploration via repertoire edges + game transitions | `/tree` → `components/tree/tree-endpoints-panel.tsx`, `components/tree/tree-explorer.tsx` | `GET /lines/tree/browse`, `GET /lines/tree/coverage`, `GET /lines/tree/branch-metrics` | **Partial** (line-tree endpoints exist; explorer currently also depends on `/tree/explorer` contract not yet represented in desktop parity map). |
| Trainer state management (`learned`, `needs_review`, streaks, priority) | `/trainer` → `components/trainer/trainer-queue.tsx`, `components/trainer/trainer-endpoints-panel.tsx` | `GET /trainer/queue`, `POST /trainer/outcomes`, `POST /trainer/priority-override` | **Gap (high impact)** (state APIs exist, but desktop learn/review interaction model is not matched yet). |
| Review propositions and branch queue decisions | `/review` → `components/review/review-actions-panel.tsx` | `GET /review/actions`, `POST /review/actions` | **Gap (high impact)** (action endpoints exist, but proposition-to-branch action loop UX and feedback is not desktop-equivalent). |

## Parity checklist by tab

Legend: `Done` = parity reached + API/UI regression coverage added. `In progress` = implemented partially. `Open` = unmet.

### 1) Overview
- [ ] **In progress** Show desktop-equivalent run-state timeline (queued/running/completed/failed with actionable CTA).
  - Backend: existing `/analysis/status`, `/analysis/progress`; add normalized run-history endpoint (`GET /analysis/runs?limit=`) if desktop timeline is required.
  - Frontend: enhance `web/src/app/(app)/overview/page.tsx` timeline panel.
  - Acceptance: user can see current + last N runs with timestamps, type, status, and error reason as on desktop.

### 2) Games
- [ ] **In progress** Desktop-style filtering/sorting and compliance-focused scanning.
  - Backend: extend `GET /games` with filter params (date, result, compliance, line, player).
  - Frontend: extend `web/src/components/games/games-table.tsx` with filter controls and persisted table state.
  - Acceptance: results and filter behavior match desktop default filters and sort order.

### 3) Game details (**high-impact priority #1**)
- [ ] **In progress** Improve navigation UX to desktop parity (sticky move list, fast jump controls, stable keyboard focus).
  - Backend: keep `GET /games/{id}`; add optional derived-navigation payload if needed (`prev_game_id`, `next_game_id`, bookmarks).
  - Frontend: enhance `web/src/components/games/game-detail.tsx` and `web/src/app/(app)/games/[id]/page.tsx`.
  - Acceptance: keyboard + button navigation mirrors desktop behavior for start/end/next/prev and preserves selected ply predictably.
- [ ] **Open** Cross-game navigation from detail view.
  - Backend: `GET /games/{id}/neighbors` or enrich `GET /games/{id}`.
  - Frontend: add previous/next game affordances near header.
  - Acceptance: user can move across games without returning to Games tab.

### 4) Lines
- [ ] **In progress** Add desktop-equivalent line drill-down from aggregated rows.
  - Backend: add line-detail endpoint (`GET /lines/{line_id}`) and optional trend endpoint (`GET /lines/{line_id}/history`).
  - Frontend: row click-through from `StatsTable` on `/lines`.
  - Acceptance: selecting a line reproduces desktop line context (coverage/compliance/time slices).

### 5) Time usage
- [ ] **In progress** Add desktop-equivalent split views (self vs opponent, in-book vs out-of-book).
  - Backend: extend `/time-usage/stats` dimensions.
  - Frontend: toggles/charts in `/time-usage` page.
  - Acceptance: user can switch between same slices shown in desktop tab.

### 6) Rating bands
- [ ] **In progress** Add desktop breakdown pivots and guardrails for band size selection.
  - Backend: keep `/rating-bands/stats`; optionally add totals/percentile metadata.
  - Frontend: enrich `/rating-bands` with desktop-equivalent summary blocks.
  - Acceptance: changing band size updates table + summary in a desktop-consistent way.

### 7) Insights
- [ ] **In progress** Add prioritization and evidence links behind each insight.
  - Backend: extend `/insights` with ranked score + source references.
  - Frontend: render confidence/rank and “open supporting rows”.
  - Acceptance: each insight shows why it appears and what action to take, matching desktop semantics.

### 8) Trainer (**high-impact priority #2**)
- [ ] **Open** Implement desktop learn/review interaction model (prompt, attempt, reveal, grade, queue progression).
  - Backend: keep `/trainer/queue`, `/trainer/outcomes`, `/trainer/priority-override`; add attempt session API if needed (`POST /trainer/sessions`, `POST /trainer/sessions/{id}/answer`).
  - Frontend: refactor `trainer-queue.tsx` + board workflow into step-based interaction state machine.
  - Acceptance: learn mode and review mode transitions, streak changes, and `needs_review` updates match desktop behavior.
- [ ] **Open** Add explicit incorrect-attempt remediation flow.
  - Backend: include next-best move and explanation fields in trainer payload.
  - Frontend: immediate remediation card on incorrect attempts.
  - Acceptance: incorrect attempts produce same remediation path as desktop.

### 9) Review (**high-impact priority #3**)
- [ ] **Open** Implement desktop proposition action loop (inspect evidence → choose action → queue/priority side effects visible immediately).
  - Backend: keep `/review/actions`; add read-after-write detail endpoint (`GET /review/actions/{id}`) and queue visibility endpoint (`GET /review/branch-queue`).
  - Frontend: upgrade `review-actions-panel.tsx` with evidence panel and post-action delta summary.
  - Acceptance: Done/Defer/Priority actions visibly update proposition state and downstream queue effects in one loop.

### 10) Tree
- [ ] **In progress** Unify tree page on parity endpoints and remove split contract ambiguity.
  - Backend: ensure one canonical tree contract (prefer `/lines/tree/*`; deprecate or implement `/tree/explorer` consistently).
  - Frontend: align `tree-explorer.tsx` with canonical endpoint set.
  - Acceptance: tree view and endpoint panel represent the same node universe and coverage values.

### 11) Settings
- [ ] **In progress** Expand runtime settings parity to desktop breadth (paths/engine/profile/fetch controls).
  - Backend: extend runtime settings schema in `GET/PUT /settings/runtime`.
  - Frontend: grouped sections and validation parity in `/settings`.
  - Acceptance: all desktop-editable settings are represented and persist correctly.

## Regression test gating (required before marking any cluster `Done`)

A cluster can only be marked `Done` after both API and UI regression checks are committed and green for that cluster.

> Note: frontend TSX unit tests currently rely on project-specific tooling (path aliases/TS transpilation). Ensure CI/frontend test runner support is wired before promoting any UI-heavy cluster to `Done`.

### Completed parity cluster with regression coverage

#### Cluster: Game details navigation baseline
- API regression tests added:
  - `tests/test_game_details_api_regression.py::test_list_games_bounds_limit_and_offset`
  - `tests/test_game_details_api_regression.py::test_get_game_returns_payload_from_read_layer`
  - `tests/test_game_details_api_regression.py::test_get_game_raises_not_found_for_missing_game`
- UI regression tests added:
  - `web/src/components/games/game-detail.test.ts` cursor-key navigation coverage including no-op and bounds behavior.
- Status: **In progress** (baseline safeguards now covered; desktop parity UX still open in high-impact items above).
