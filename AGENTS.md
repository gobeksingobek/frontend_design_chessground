# AGENTS.md

## Purpose
This repository contains a chess repertoire analysis system with desktop, backend, PostgreSQL storage, Redis-backed workers, and a Next.js web client.

## Target architecture and hard invariants
- PostgreSQL is the only runtime source of truth for persisted application, analysis, configuration, job, and result data.
- Do not introduce SQLite code, local database files, or alternate runtime persistence backends.
- Desktop and web clients access persisted data through the backend API; they do not connect directly to PostgreSQL.
- Redis Streams are the execution backbone for server-side analysis, import/fetch, reanalysis, and other long-running work.
- PostgreSQL is authoritative for job lifecycle, idempotency, progress, retries, errors, and results. Redis messages are transient delivery signals and must be safe to replay.
- Canonical or persisted Stockfish analysis runs on Redis-backed server workers.
- Browser Stockfish/WASM is limited to bounded advisory quick evaluation. Persisted results must be recomputed or validated by server workers.
- Repertoire and game source PGNs required for reproducible analysis are stored in PostgreSQL, not only referenced by local filesystem paths.
- Keep heavy computation in workers. API, desktop, and web request work and display persisted results.

## Job and data contracts
- Use capability streams `chessground:jobs:orchestration`, `chessground:jobs:engine`, and `chessground:jobs:ingest`; each has its own consumer group and dead-letter stream.
- Redis messages contain identifiers and attempt metadata only. Durable payloads belong in `analysis_job_steps`.
- Workers claim PostgreSQL steps conditionally, acknowledge Redis only after result state commits, heartbeat leases, and tolerate duplicate delivery.
- Scope user-owned data and idempotency to `workspace_id`. The API derives the current workspace; clients do not select arbitrary workspaces.
- Keep globally reusable positions and engine cache entries deduplicated. Scope repertoire, games, trainer/review state, settings, jobs, source artifacts, and derived user data by workspace.
- Readers must use `workspace_state.active_analysis_run_id` so an incomplete replacement run never displaces the last completed result set.

## Repository map
- `backend/api_service.py`: authenticated FastAPI contracts and durable job enqueueing.
- `backend/worker_service.py`: capability-specific Redis consumer and durable claim/retry/ack logic.
- `backend/orchestration.py`, `backend/analysis_results.py`, `backend/ingest_workflows.py`: server-side analysis orchestration, finalization, and ingest.
- `backend/jobs.py`, `backend/worker_repository.py`, `backend/migrations.py`, `backend/db.py`: durable job access, synchronous worker persistence, schema migrations, and API database access.
- `storage/postgres/migrations/`: ordered canonical PostgreSQL migrations. Do not add runtime bootstrap SQL elsewhere.
- `analysis/`, `matching/`, `parsing/`: computation and parsing without persistence ownership.
- `main.py`, `gui/`, `app_config.py`: API-backed desktop client and local client-only configuration.
- `web/`: Next.js frontend; follow `web/README.md` for its established component and layout conventions.
- `tests/`: unit and contract tests plus service-backed integration tests.

## Import and configuration rules
- Repertoire and game upload endpoints accept a single `.pgn` or a `.zip` containing PGNs. Database dumps are not import formats.
- Uploaded and fetched PGN text is persisted in `source_artifacts` before asynchronous ingest.
- `config/settings.ini` contains desktop client settings only: backend URL, API token reference, piece assets, and optional local upload directories.
- Workspace analysis and fetch settings live in PostgreSQL `runtime_settings`.
- Stockfish executable paths and worker CPU/process tuning are deployment configuration, never desktop or web runtime settings.

## Engineering workflow
- For implementation requests, gather the relevant context, make reasonable low-risk assumptions, and carry the work through implementation and proportionate verification. Ask only when a missing decision would materially change the result.
- Search for existing implementations and helpers before adding new abstractions. Follow established naming, formatting, typing, localization, and UI conventions.
- Prefer root-cause fixes and coherent changes across every affected surface; do not leave knowingly partial API, backend, desktop, worker, or web wiring.
- Preserve behavior outside the requested scope. Add or update tests when behavior changes, and keep error handling explicit rather than swallowing failures or returning success-shaped fallbacks.
- Read enough surrounding code before editing, batch related changes, and preserve unrelated worktree changes.
- When asked for a code review, lead with actionable findings ordered by severity and include file and line references. If there are no findings, say so and identify any residual testing gaps.

## Frontend design direction
- For a new design or major redesign, establish a clear visual concept before implementation, covering typography, palette, hierarchy, spacing, surfaces, iconography, and motion. Preserve product behavior and information architecture where useful, but do not treat the current visual styling as a constraint.
- Keep the shared component architecture described in `web/README.md`, but evolve its primitives, variants, and semantic theme tokens so the new direction is cohesive across the application rather than implemented as page-specific decoration.
- Treat typography as a deliberate product decision. Do not default to Inter, Times New Roman, Arial, Roboto, or an unstyled system stack as the primary UI font. Choose a distinctive, highly legible family appropriate for a chess-analysis product, load it centrally, and expose it through shared theme tokens and consistent fallbacks.
- Avoid generic, interchangeable dashboard composition. Use strong hierarchy, purposeful spacing, and chess-analysis-specific presentation, with a recognizable identity that remains practical for dense analysis workflows.
- Use color, layered surfaces, and restrained visual texture intentionally. Avoid arbitrary gradients, raw colors, default purple-on-white styling, or a dark theme chosen only because it looks technical.
- Keep motion purposeful and lightweight, and verify the redesigned UI at mobile, tablet, and desktop widths in both light and dark themes.

## Validation commands
- Python unit/contract tests: `python -m pytest -q`
- Apply PostgreSQL migrations: `python -m backend.bootstrap_postgres_schema`
- Validate migrations without applying: `python -m backend.bootstrap_postgres_schema --validate-only`
- Service-backed tests: set `RUN_INTEGRATION_TESTS=1`, `POSTGRES_DSN`, and `REDIS_URL`, then run `python -m pytest -q -m integration`
- Web UI regression tests: `npm --prefix web run test:ui-regression`
- All frontend/API contract checks: `npm --prefix web run check:contracts`
- Web lint: `npm --prefix web run lint`
- Web type check: `npm --prefix web run typecheck`
- Web production build: `npm --prefix web run build`

## Change safety and handoff
- Prefer the smallest safe change, but do not preserve behavior by reintroducing client-side persistence or in-process long-running jobs.
- Do not edit an applied migration; add a new ordered migration.
- For persistence, job, or cutover changes, run real PostgreSQL/Redis integration coverage in addition to unit fakes.
- Summaries and PRs should state what changed, why, checks run, migration/deployment impact, and any explicit follow-up.
