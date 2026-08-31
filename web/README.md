# ChessGround Web

## UI regression tests

Run the canonical UI regression suite with:

```bash
npm run test:ui-regression
npm run check:contracts
```

The command uses Node's test runner with a local loader that transpiles TS/TSX and resolves the `@/` alias to `web/src/*`, matching application imports.

## Repertoire import upload format

The web app supports repertoire import through `POST /repertoires/import`.

Accepted upload formats:

1. **Zip archive (`.zip`) containing PGN files**
   - The archive can include nested folders.
   - The backend recursively scans for `*.pgn` and `*.PGN` files.
2. **Single PGN file (`.pgn`)**

Not accepted:
- Database snapshots (`.db`, `.sql`) are not currently importable from the web endpoint.
- Archives without any PGN files.

Duplicate protection:
- `Idempotency-Key` prevents duplicate job creation for a repeated request.
- Content hashes deduplicate source artifacts within a workspace.
- Already known canonical repertoire line path hashes are skipped during ingest and reported in the job result.

## Frontend UI architecture

The Next.js frontend should use the shared UI architecture in this directory so new pages and features look and behave consistently. Keep implementation organized around these primary areas:

- `web/src/app/` for route-level page shells, layouts, and data-entry points.
- `web/src/components/ui/` for shared UI primitives and composable presentation building blocks.
- `web/src/components/chess/` for board-centric interaction patterns, move playback, and chess-specific display elements.
- `web/src/components/games/` for game list, game detail, and related domain-specific presentation pieces.

### Core principles

- **Tailwind-first styling:** Prefer Tailwind utility classes for layout, spacing, typography, borders, and state styling before adding bespoke CSS. Reach for shared utility patterns and component variants before inventing one-off page classes.
- **Semantic theme tokens:** Use semantic color, surface, border, and text tokens rather than hard-coded values so themes remain consistent and maintainable. New visual treatments should extend the shared token system instead of bypassing it.
- **Reusable UI primitives:** Build common cards, buttons, inputs, tabs, badges, dialogs, and status treatments from the primitives in `web/src/components/ui/`. If a pattern is likely to repeat, promote it into a shared primitive or variant rather than duplicating markup across pages.
- **Dashboard layout conventions:** Pages under `web/src/app/` should follow the existing app-shell and dashboard structure with consistent page padding, vertical rhythm, section grouping, and header actions. Major content areas should read as part of one cohesive product surface, not isolated microsites.
- **Dark mode support:** Every new UI surface must be designed and verified for dark mode. Text contrast, board-adjacent surfaces, overlays, dividers, and interactive states should remain legible and visually balanced in both light and dark themes.
- **Responsive design:** Design mobile-first and validate layouts at common phone, tablet, and desktop widths. Grids, panels, headers, tables, and chess-related controls should stack or reflow cleanly without clipping or forcing awkward horizontal scrolling.
- **Board and move interaction animation:** Keep animation purposeful and lightweight, especially around board state changes, move navigation, highlights, and status transitions. Favor subtle transitions that reinforce move flow and feedback, and avoid decorative motion that distracts from analysis or play.

### Do not

- Do not add page-specific ad hoc styling when an existing shared component, primitive, or variant in `web/src/components/ui/` can be used or extended.
- Do not use inline styles except for truly dynamic runtime values that cannot be expressed cleanly through Tailwind classes or the shared token system.
- Do not introduce new raw color hex values outside the shared theme and semantic token system.

### When adding a new page

- [ ] Start from the appropriate page shell and layout conventions in `web/src/app/` so navigation, spacing, and dashboard framing remain consistent.
- [ ] Use shared section headers and action areas that match existing page hierarchy and information density.
- [ ] Include a clear loading state using shared primitives or skeleton patterns where data is asynchronous.
- [ ] Include an intentional empty state with helpful copy and next actions when no data is available.
- [ ] Verify the page at mobile widths to ensure controls, boards, lists, and tables remain usable without layout breakage.
