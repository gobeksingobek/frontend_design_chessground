# AGENTS.md

## Purpose
This repository contains a chess repertoire analysis system with desktop, backend, storage, and web surfaces. Use this file as the default operating guide for implementation work in this repo.

## Default working style
- Prefer the smallest safe change that satisfies the user request.
- Treat long-form planning docs as guidance unless the task is explicitly about parity, release readiness, or a larger architecture change.
- Preserve existing behavior unless the task clearly asks to extend or replace it.

## Hard invariants
- PostgreSQL is the source of truth for persisted analysis data.
- Runtime features that depend on stored analysis should continue to work from persisted data, not only transient in-memory state.
- Keep heavy computation in the analysis/backend path when practical; GUI and web surfaces should primarily read and display persisted results.
- Repertoire import through the current web/API path accepts `.zip` archives containing PGNs or single `.pgn` files; `.db` and `.sql` snapshots are not accepted there.
- Redis Streams are used as transient queue transport for sideline/background job workflows; request state and results belong in Postgres.

## Repo map
- `backend/`: API and worker-oriented backend services.
- `analysis/`, `matching/`, `parsing/`, `storage/`: core analysis, matching, parsing, and persistence logic.
- `gui/`: desktop application UI.
- `web/`: Next.js web frontend.
- `config/`: runtime configuration, including `config/settings.ini`.
- `docs/`: parity, release, and implementation guidance.
- `tests/`: automated tests.

## Architecture guidance
- The desktop app loads runtime settings from `config/settings.ini`.
- Repertoire and game PGNs are parsed by the analysis pipeline.
- Parsed data, matches, and derived analysis are stored in PostgreSQL.
- The desktop GUI and web surfaces should primarily read precomputed data rather than recomputing heavy analysis inline.
- Prefer incremental or additive schema/UI changes over disruptive rewrites.

## Frontend guidance
When working in `web/`, also follow `web/README.md`:
- use shared UI primitives and layout conventions;
- prefer Tailwind-first styling;
- support dark mode and responsive layouts;
- avoid ad hoc page-specific styling when a shared primitive or variant can be reused.

## Release-time guidance references
These documents are important, but they are not universal blockers for every small task unless the user explicitly asks for that scope:
- `docs/web_desktop_parity_checklist.md`
- `docs/release_cutover_checklist.md`
- `suggestions.txt`

## Validation expectations
- Run the smallest relevant tests/checks for the area you changed.
- Prefer targeted verification before broad suites when making narrow changes.
- If you change the web UI, use the documented web test commands when feasible.

## Change safety
- Do not casually change config formats, persistence contracts, or import behavior.
- Do not move heavy computation into UI layers without an explicit reason.
- Do not treat aspirational design guidance as a hard requirement for unrelated bug fixes.

## Handoff notes
In summaries and PRs, explain:
- what changed;
- why the approach is intentionally scoped;
- what checks were run;
- any follow-up work that remains out of scope.
