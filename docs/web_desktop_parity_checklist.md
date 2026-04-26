# Desktop ↔ Web parity checklist

This checklist uses `docs/desktop_capabilities_inventory.md` as the source of truth and maps each desktop capability to concrete web surfaces.

## How to use this document

Use this file as a planning and release-readiness backlog. It is intended to guide parity work and clarify what “Done” means for parity-focused efforts. It should not be treated as a hard blocker for every implementation task in the repository.

For routine coding tasks, contributors and coding agents may ship narrowly scoped improvements without satisfying every parity row below, unless the task explicitly involves parity status, cutover readiness, or desktop-dependency removal.

## Capability-to-surface map (source-of-truth mapping)

## Wiring status (current)

- This document is now the **tracked engineering backlog** for closing desktop/web parity.
- Every row below has an owner-ready scope: exact backend contract changes, exact frontend files, and parity tests (API + UI).
- Priority is ordered by product risk and user impact.

| Desktop capability (inventory) | Web frontend route(s) + component(s) | Backend endpoint(s) | Parity state |
| --- | --- | --- | --- |
| Loads/persists runtime configuration (`config/settings.ini`) | `/settings` → `web/src/app/(app)/settings/page.tsx` | `GET /settings/runtime`, `PUT /settings/runtime` | **In progress** |
| Imports repertoire/game PGNs and runs matching/compliance analysis | `/overview`, `/repertoires`, `/games` → `overview/page.tsx`, `repertoires/page.tsx`, `games/page.tsx` | `POST /repertoires/import`, `POST /analysis/run/full`, `POST /analysis/run/fetch-games`, `GET /games` | **In progress** |
| Runs Stockfish analysis and stores per-ply eval metrics | `/overview`, `/games/[id]`, `/analysis` → `overview/page.tsx`, `games/[id]/page.tsx`, `components/analysis/sideline-analysis-form.tsx` | `POST /analysis/run/engine-only`, `POST /analysis/run/full`, `GET /games/{game_id}`, `POST /sidelines` | **In progress** |
| Computes/stores aggregate stats (lines, time, rating, insights) | `/overview`, `/lines`, `/time-usage`, `/rating-bands`, `/insights`, `/review` | `GET /overview/summary`, `GET /lines/stats`, `GET /time-usage/stats`, `GET /rating-bands/stats`, `GET /insights`, `GET /review/items` | **In progress** |
| Supports tree exploration via repertoire edges + game transitions | `/tree` → `components/tree/tree-endpoints-panel.tsx`, `components/tree/tree-explorer.tsx` | `GET /lines/tree/browse`, `GET /lines/tree/coverage`, `GET /lines/tree/branch-metrics` | **In progress** |
| Trainer state management (`learned`, `needs_review`, streaks, priority) | `/trainer` → `components/trainer/trainer-queue.tsx`, `components/trainer/trainer-endpoints-panel.tsx` | `GET /trainer/queue`, `POST /trainer/outcomes`, `POST /trainer/priority-override` | **Open (high impact)** |
| Review propositions and branch queue decisions | `/review` → `components/review/review-actions-panel.tsx` | `GET /review/actions`, `POST /review/actions` | **Open (high impact)** |

## Prioritized implementation backlog (tracked engineering tasks)

Legend: `Open` = not started, `In progress` = partially implemented, `Done` = merged + parity evidence is in place and the relevant parity tests are green.

### P0 — Trainer interaction model parity (highest impact)

| Task ID | Status | Backend endpoint contract changes | Frontend component/page changes | Parity acceptance tests (API + UI) |
| --- | --- | --- | --- | --- |
| TRN-01 step-based trainer session loop | Done | Add `POST /trainer/sessions` with request `{ mode: "learn" | "review", line_id?: string }` and response `{ session_id, item: { branch_id, fen, prompt, expected_move_uci, difficulty }, queue_snapshot: { remaining, learned, needs_review } }`.<br>Add `POST /trainer/sessions/{session_id}/answer` with request `{ move_uci, elapsed_ms }` and response `{ outcome: "correct" | "incorrect", grade: "again" | "hard" | "good" | "easy", streak_delta, item_state: "learned" | "needs_review", next_item?: {...}, remediation?: {...} }`. | Refactor `web/src/components/trainer/trainer-queue.tsx` into explicit state machine stages: `prompt -> attempt -> reveal -> grade -> next`.<br>Update `web/src/app/(app)/trainer/page.tsx` to drive mode selection and session lifecycle from `session_id` instead of implicit queue pulls. | API: add `tests/test_trainer_sessions_api.py` for session creation, answer grading, queue snapshot transitions, and invalid session handling.<br>UI: add `web/src/components/trainer/trainer-queue.test.ts` for stage transitions, grade button behavior, and deterministic queue progression mocks.<br>Contract: add `web/scripts/check-trainer-contract.mjs` validating required JSON keys for both new endpoints. |
| TRN-02 incorrect-attempt remediation parity | Done | Extend `POST /trainer/sessions/{session_id}/answer` response `remediation` object with exact fields `{ best_move_uci, principal_variation: string[], explanation_markdown, retry_required: boolean }` when `outcome="incorrect"`.<br>Ensure `POST /trainer/outcomes` remains backward-compatible and maps to session grading semantics. | In `web/src/components/trainer/trainer-queue.tsx`, render remediation card immediately after incorrect answer with best move, PV line, and retry CTA.<br>Add a remediation summary section in `web/src/components/trainer/trainer-endpoints-panel.tsx` for endpoint verification visibility. | API: extend `tests/test_trainer_sessions_api.py` with remediation payload shape assertions.<br>UI: extend `web/src/components/trainer/trainer-queue.test.ts` with incorrect-answer remediation rendering and retry flow assertions.<br>Contract: extend `web/scripts/check-trainer-contract.mjs` for remediation field presence and types. |

### P0 — Review action loop parity (highest impact)

| Task ID | Status | Backend endpoint contract changes | Frontend component/page changes | Parity acceptance tests (API + UI) |
| --- | --- | --- | --- | --- |
| REV-01 proposition inspect → action → queue delta loop | Done | Add `GET /review/actions/{action_id}` response `{ action_id, proposition_id, evidence: { game_ids: string[], line_refs: string[], eval_delta_cp }, recommended_action, created_at }`.<br>Canonicalize `GET /review/branch-queue` to return a **plain array** `[{ proposition_id, queue_status, queued_at, proposition_status, evidence_count, threshold_count, pos_id, uci_move, line_id_hint, updated_at }]` (no envelope object).<br>Extend `POST /review/actions` response with `{ action_id, proposition_id, applied: true, queue_delta: { added_branch_ids: string[], reprioritized_branch_ids: string[] } }`. | Upgrade `web/src/components/review/review-actions-panel.tsx` with split panes: proposition evidence inspector, action controls, and post-action queue delta summary.<br>Update `web/src/app/(app)/review/page.tsx` to fetch and refresh `branch-queue` immediately after action submit. | API: add `tests/test_review_actions_api.py` for action detail retrieval, action write response shape, and branch queue read-after-write consistency.<br>UI: add `web/src/components/review/review-actions-panel.test.ts` for full loop: inspect evidence, choose action, verify immediate queue delta display.<br>Contract: add `web/scripts/check-review-contract.mjs` for required response fields and enum values (including array-only `branch-queue`). |

### P1 — Game-detail cross-game + keyboard parity hardening

| Task ID | Status | Backend endpoint contract changes | Frontend component/page changes | Parity acceptance tests (API + UI) |
| --- | --- | --- | --- | --- |
| GMD-01 keyboard/navigation behavior parity | Done | Enrich `GET /games/{id}` payload with `navigation` object: `{ current_game_id, prev_game_id, next_game_id, bookmarked_ply_ids: number[], can_jump_start: boolean, can_jump_end: boolean }` (all nullable where appropriate). | Harden `web/src/components/games/game-detail.tsx` keyboard handlers for `Home/End/ArrowLeft/ArrowRight` plus stable focus retention after ply updates.<br>Update `web/src/app/(app)/games/[id]/page.tsx` to consume `navigation` and keep selected ply state across rerenders. | API: extend `tests/test_game_details_api_regression.py` with `navigation` object schema assertions and null-edge cases for first/last games.<br>UI: extend `web/src/components/games/game-detail.test.ts` with focus retention and start/end jump parity checks.<br>Contract: add `web/scripts/check-game-detail-contract.mjs` for `navigation` shape validation. |
| GMD-02 cross-game traversal from detail header | Done | Canonical neighbors contract is now the `GET /games/{id}` payload fields: `prev_game_id`, `next_game_id`, optional `prev_game_label`, optional `next_game_label`.<br>`GET /games/{id}/neighbors` is not a canonical contract and is not required by web callers. | Previous/next game controls and Alt+Arrow traversal in `web/src/components/games/game-detail.tsx` preserve `ply`, selected tab, and board orientation via route query params during cross-game navigation.<br>`web/src/app/(app)/games/[id]/page.tsx` restores tab/orientation state from query params. | API: regression coverage in `tests/test_game_details_api_regression.py` now asserts first/middle/last traversal IDs and optional labels through `GET /games/{id}`.<br>UI: `web/src/components/games/game-detail.test.ts` includes route-query preservation helper coverage for cross-game traversal state.<br>Contract: `web/scripts/check-game-detail-contract.mjs` enforces `GET /games/{id}` as the single canonical neighbors source. |

### P1 — Stats drill-down/pivot parity (lines, time usage, rating bands)

| Task ID | Status | Backend endpoint contract changes | Frontend component/page changes | Parity acceptance tests (API + UI) |
| --- | --- | --- | --- | --- |
| STS-01 lines drill-down context parity | Done | Canonicalize on existing `GET /lines/stats/{line_id}` for line detail (`{ line_id, total_games, compliance_rate, ... }`) and `GET /lines/stats/{line_id}/history` for trend buckets (`{ line_id, buckets, totals }`).<br>Do not introduce `/lines/{line_id}` aliases; if present, treat them as non-canonical compatibility paths. | Add row click-through from `/lines` table in `web/src/app/(app)/lines/page.tsx` to a detail drawer/panel rendered by `web/src/components/stats/stats-table.tsx` integration hooks. | API: keep `tests/test_lines_stats_api.py` as the parity contract test for detail + history route/payload shape.<br>UI: add `web/src/components/stats/stats-table.test.ts` for row selection, detail rendering, and history tab toggles.<br>Contract: keep `web/scripts/check-lines-contract.mjs` aligned to `/lines/stats/{line_id}` and `/lines/stats/{line_id}/history`. |
| STS-02 time-usage pivot parity | Done | Extend `GET /time-usage/stats` to require `pivot` query enum (`self_vs_opp`, `in_book_vs_out_of_book`) and return `{ pivot, buckets: [...], totals: {...} }`. | Add pivot toggle controls in `web/src/app/(app)/time-usage/page.tsx` and update `web/src/components/stats/stats-table.tsx` column model based on selected pivot. | API: add `tests/test_time_usage_stats_api.py` for both pivot modes and invalid pivot handling.<br>UI: add `web/src/components/stats/stats-table.test.ts` cases for pivot toggle and column swap behavior.<br>Contract: add `web/scripts/check-time-usage-contract.mjs` for pivot enum and response keys. |
| STS-03 rating-bands drill-down/pivot parity | In progress | Extend `GET /rating-bands/stats` with `band_size` guardrails (`min/max/step`) and response metadata `{ band_size, allowed_band_sizes, percentiles, totals }`. | In `web/src/app/(app)/rating-bands/page.tsx`, enforce guardrails in selector controls and render desktop-equivalent summary blocks using metadata fields. | API: add `tests/test_rating_bands_api.py` for guardrails, metadata presence, and recomputation behavior when `band_size` changes.<br>UI: add `web/src/components/stats/stats-table.test.ts` for band-size selector constraints and summary updates.<br>Contract: add `web/scripts/check-rating-bands-contract.mjs` for metadata and guardrail fields. |

### P2 — Remaining parity backlog

| Task ID | Status | Backend endpoint contract changes | Frontend component/page changes | Parity acceptance tests (API + UI) |
| --- | --- | --- | --- | --- |
| OVR-01 overview run-state timeline parity | In progress | Add `GET /analysis/runs?limit={n}` response `{ runs: [{ run_id, run_type, status, started_at, finished_at, error_reason }] }` normalized across engine/full/fetch runs. | Enhance `web/src/app/(app)/overview/page.tsx` timeline panel with current + recent run cards and action CTAs. | API: add `tests/test_analysis_runs_api.py` for ordering and status transitions.<br>UI: add `web/src/app/(app)/overview/page.test.tsx` timeline rendering and retry CTA behavior.<br>Contract: add `web/scripts/check-analysis-runs-contract.mjs`. |
| GMS-01 games list filter/sort parity | In progress | Extend `GET /games` query params: `date_from`, `date_to`, `result`, `compliance_min`, `line_id`, `player`, `sort_by`, `sort_dir` with deterministic defaults matching desktop. | Extend `web/src/components/games/games-table.tsx` filter controls and persist state in URL/query storage from `web/src/app/(app)/games/page.tsx`. | API: add `tests/test_games_list_filters_api.py` for filter combinations + default ordering.<br>UI: add `web/src/components/games/games-table.test.ts` for control interactions and persisted state restore.<br>Contract: add `web/scripts/check-games-list-contract.mjs`. |
| INS-01 insights priority/evidence parity | In progress | Extend `GET /insights` rows with `{ priority_score, confidence, source_refs: [{ type, id, label }] }`. | Update `web/src/app/(app)/insights/page.tsx` to render rank/confidence and “open supporting rows” interactions. | API: add `tests/test_insights_api.py` for sorted priority semantics and source reference presence.<br>UI: add `web/src/app/(app)/insights/page.test.tsx` for evidence drawer interactions.<br>Contract: add `web/scripts/check-insights-contract.mjs`. |
| TRE-01 tree canonical contract parity | In progress | Canonicalize on `/lines/tree/*` endpoints and either remove `/tree/explorer` use or enforce identical response schema with explicit deprecation timeline. | Align `web/src/components/tree/tree-explorer.tsx` and `tree-endpoints-panel.tsx` to one canonical schema adapter. | API: add `tests/test_tree_contract_api.py` for browse/coverage/branch-metrics schema consistency.<br>UI: add `web/src/components/tree/tree-explorer.test.ts` for node identity + coverage consistency across panels.<br>Contract: add `web/scripts/check-tree-contract.mjs`. |
| SET-01 runtime settings breadth parity | In progress | Extend `GET/PUT /settings/runtime` schema to include desktop-editable groups: paths, engine, profile, fetch controls; return field-level validation errors `{ field, code, message }[]`. | Expand `web/src/app/(app)/settings/page.tsx` into grouped sections and inline validation messaging mapped from backend errors. | API: add `tests/test_settings_runtime_api.py` for full schema round-trip and validation codes.<br>UI: add `web/src/app/(app)/settings/page.test.tsx` for grouped form behavior + error display.<br>Contract: add `web/scripts/check-settings-contract.mjs`. |

## Cutover gate (desktop dependency removal)

Desktop dependency should be removed only when all backlog tasks above are marked `Done` and the following regression gates are continuously green in CI. This gate applies to cutover/release decisions, not to unrelated implementation work:

1. Python/API regressions in `tests/` covering every changed endpoint contract.
2. Web component/page tests in `web/src/components/**/*.test.ts` (and page tests where applicable) covering each parity interaction loop.
3. Web/API contract checks in `web/scripts/*` validating required request/response schemas.
4. Existing UI regression workflow parity command remains green:

```bash
npm --prefix web run test:ui-regression
```

### Done criteria per row

A row should move to `Done` only when all of the following are true:

- Endpoint contracts are implemented and documented in code-level types/schemas.
- Frontend implementation is merged and wired to live backend contracts (no placeholder mocks for runtime paths).
- At least one API regression test and one UI regression test for that row are merged and green.
- Corresponding `web/scripts/*` contract check exists and passes in CI.
- No desktop-only fallback path is required for the same user journey.
