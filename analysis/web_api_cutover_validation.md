# Web/API Cutover Validation Report

Date: 2026-03-02  
Repo: `ChessGround`

## Scope requested

- Validate web flows against API for:
  - `/overview`
  - `/games`
  - `/games/{id}`
  - `/sidelines`
- Check auth/CORS behavior from:
  - `https://<web>.onrender.com`
  - `http://localhost:3000`
- Confirm expected Postgres-backed data appears on pages.
- Record gaps that still depend on local/SQLite-only workflows (`main.py` desktop paths).
- Produce cutover action lists.

## Validation approach

Because live Render endpoints were not reachable from this environment (proxy `CONNECT tunnel failed`), this validation was performed via:

1. Static flow tracing in Next.js page/components and shared API client.
2. Backend auth/CORS and data-backend behavior review in FastAPI service and settings.
3. Runtime connectivity checks attempted against likely Render API hostname and localhost.

## Flow validation (web route -> API endpoint)

### 1) `/overview`

- Route renders `SidelineTable`, so it calls `listSidelines(20)`.
- API call is `GET {API_BASE_URL}/sidelines?limit=20` with bearer auth header.
- Result: this page is **not a summary endpoint** today; it is effectively a sideline-jobs table view.

### 2) `/games`

- Route renders `GamesTable`, which calls `listGames(50,0)`.
- API call is `GET {API_BASE_URL}/games?limit=50&offset=0` with bearer auth.
- Returned rows are displayed as date/players/result/compliance/line id.

### 3) `/games/{id}`

- Route parses numeric `id`, renders `GameDetail`.
- `GameDetail` calls `getGame(gameId)` -> `GET {API_BASE_URL}/games/{id}`.
- Same screen includes sideline creation via `SidelineAnalysisForm` using
  `POST {API_BASE_URL}/sidelines` with `Idempotency-Key` + bearer token.

### 4) `/sidelines`

- Route renders `SidelineTable`, identical API flow to `/overview`.
- API call is `GET {API_BASE_URL}/sidelines?limit=20` with bearer auth.

## Auth + CORS behavior

## Authentication

- API requires `Authorization: Bearer <token>` for `/games*` and `/sidelines*` routes.
- Web client token source precedence:
  1. `localStorage` token from login form
  2. fallback `NEXT_PUBLIC_API_TOKEN` env
  3. default literal `dev-token` if env not set
- Implication:
  - If Render API token differs from web token, all protected route fetches fail 401.

## CORS

- CORS middleware is only enabled when `API_CORS_ORIGINS` is configured.
- If unset, browser-origin requests from both `https://<web>.onrender.com` and `http://localhost:3000` will fail CORS preflight (even with valid auth token).
- If set, exact origins must be present in allow-list, e.g.
  - `https://<web>.onrender.com`
  - `http://localhost:3000`

## Postgres-backed data confirmation

- API is designed to enforce/read Postgres in Render (`DATA_BACKEND=postgres`, `ENFORCE_POSTGRES_ON_RENDER=1`).
- Required analysis schema (`positions`, `games`, `game_positions`, `matches`, `analysis_ply`) is validated at startup and auto-applied when missing SQL is available.
- Web pages are wired to API read routes for live data (`/games`, `/games/{id}`, `/sidelines`).

### Current validation status

- **Could not directly verify deployed Postgres rows rendering in the browser** from this environment due outbound proxy blocking to Render.
- Local repo SQLite file (`data/analysis.db`) has no tables in this environment, so local fallback rendering could not be used as a substitute dataset.

## Gaps still tied to local/SQLite desktop workflow

1. Primary documented end-to-end workflow remains desktop-first (`python main.py`), including local path prompts and settings for PGN folders, Stockfish path, and piece image assets.
2. Data ingest/analysis is still documented and implemented around local SQLite outputs from desktop runs before optional backfill to Postgres.
3. Some operational paths (analysis recomputation, fetch workflows) are still described in desktop-tab terms rather than pure web/API jobs.
4. If Postgres backfill/bootstrap steps are skipped or stale, web pages have no guaranteed dataset source.

## Must-fix before full cutover

1. **Run a live smoke validation from an environment with Render access**:
   - Login through web app
   - Open `/overview`, `/games`, `/games/{id}`, `/sidelines`
   - Verify successful API responses + non-empty expected data.
2. **Set/verify API CORS origins include both required origins**:
   - `https://<web>.onrender.com`
   - `http://localhost:3000` (if local web dev against remote API is required)
3. **Ensure token parity** between `NEXT_PUBLIC_API_TOKEN` and `API_AUTH_TOKEN` (or explicit browser token entry process).
4. **Confirm Postgres schema bootstrap + backfill in deploy pipeline** completed successfully for production dataset.
5. **Define acceptance criteria for `/overview`** (currently sideline table only, not a true overview dashboard).

## Post-cutover improvements

1. Replace token-in-localStorage login with managed auth/session flow.
2. Add automated browser/API contract tests for the four routes in CI.
3. Add explicit health/readiness endpoint checks to deployment verification.
4. Add server-side pagination/filtering on `/games` and `/sidelines` for scale.
5. Implement dedicated overview metrics endpoint/page instead of duplicating sidelines table.
6. Add synthetic seed/smoke data fixture for non-production environment validation.

## Commands run

```bash
rg -n "onrender|NEXT_PUBLIC_API_BASE_URL|API_CORS_ORIGINS|API_AUTH_TOKEN" -S
curl -sS -D - https://chessground-api.onrender.com/health -o /tmp/health.out && head -n 20 /tmp/health.out
python - <<'PY'
import sqlite3
conn=sqlite3.connect('data/analysis.db')
cur=conn.cursor()
print(cur.execute("select name from sqlite_master where type='table' order by 1").fetchall())
PY
```

