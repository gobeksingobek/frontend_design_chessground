# Backend services

This directory introduces two deployable backend processes that keep Neon/Postgres as source of truth while using Redis Streams for transient queueing.

## Services

- `backend.api_service:app` (FastAPI)
  - Validates sideline creation payloads.
  - Requires bearer token auth (`API_AUTH_TOKEN`).
  - Enforces idempotency (`Idempotency-Key`) via a unique Postgres constraint.
  - Writes request records to Postgres, then enqueues jobs to Redis Streams.
  - Exposes read APIs for request status.
  - `GET /games` and `GET /games/{game_id}` for web games/game-detail screens.
  - Validates analysis schema at startup when `DATA_BACKEND=postgres` (fails fast if required tables are missing).
  - Enforces `DATA_BACKEND=postgres` on Render by default (`ENFORCE_POSTGRES_ON_RENDER=1`).
  - Supports CORS origin allow-list via `API_CORS_ORIGINS`.

- `backend.worker_service`
  - Uses Redis consumer groups for horizontal scaling.
  - Claims queued/retry jobs from Postgres to provide exactly-once-ish behavior.
  - Runs Stockfish branch analysis and writes results back to Postgres.
  - Retries failed work up to `SIDELINE_MAX_RETRIES`; sends exhausted jobs to a dead-letter stream.

## Queue semantics

- Main stream: `SIDELINE_STREAM_NAME` (default `sideline:jobs`).
- Dead-letter stream: `SIDELINE_DEAD_LETTER_STREAM` (default `sideline:jobs:dead`).
- Consumer group: `SIDELINE_CONSUMER_GROUP` (default `sideline-workers`).
- Idempotency key uniqueness is persisted in Postgres (`sideline_requests.idempotency_key`).

## Run

Install the locked server environment first:

```bash
uv sync --locked --no-dev
```

```bash
uv run --no-sync uvicorn backend.api_service:app --host 0.0.0.0 --port 8000
uv run --no-sync python -m backend.worker_service
```

## Bootstrap and backfill commands

Before running API in Postgres mode, bootstrap schema once:

```bash
uv run --no-sync python -m backend.bootstrap_postgres_schema
```

Validate schema only:

```bash
uv run --no-sync python -m backend.bootstrap_postgres_schema --validate-only
```

Postgres-only deployment no longer uses local database backfill scripts.


## Required env vars

- `POSTGRES_DSN` (Neon/Postgres DSN)
- `REDIS_URL`
- `API_AUTH_TOKEN`
- `DATA_BACKEND` (`postgres` recommended; Render defaults to postgres mode)
- `STOCKFISH_PATH`

Optional tuning:

- `API_CORS_ORIGINS` (comma-separated list such as `https://your-web.onrender.com`)
- `ENFORCE_POSTGRES_ON_RENDER` (`1` by default)
- `SIDELINE_MAX_RETRIES`
- `SIDELINE_STREAM_BLOCK_MS`
- `SIDELINE_CONSUMER_NAME`
- `STOCKFISH_DEPTH`

## API contract (Phase 0)

The API now documents request/response and error envelopes in OpenAPI:

- `POST /sidelines`
  - Headers:
    - `Authorization: Bearer <API_AUTH_TOKEN>`
    - `Idempotency-Key: <client-generated-key>`
  - On duplicate idempotency key, returns the existing `SidelineResponse` row.

- `GET /sidelines/{request_id}`
  - Returns `404` with an error envelope when the request does not exist.

- `GET /sidelines?limit=20`
  - `limit` is bounded to `[1, 100]` server-side.

Standardized API errors use:

```json
{
  "detail": {
    "error_code": "NOT_FOUND",
    "detail": "Sideline request not found"
  }
}
```

Validation failures are returned via FastAPI's `422` structure and are explicitly documented in the route responses.


Phase 3 note: `GET /games/{game_id}` move payload now includes `fen` for each move, enabling sideline enqueue actions from the web game-detail UI.



## Production promotion checklist

Use the following checklist when promoting staging configuration to production:

1. Run a parity pass in staging and promote to production only after parity succeeds.
2. Keep `DATA_BACKEND=postgres` permanently in Render for API and worker services.
3. Do not allow production paths to read from or write to local file-based databases directly.
4. Tag the release immediately after promotion, then monitor API and worker logs for the first 24 hours.
5. Keep a rollback plan with both the previous service revision and a known-good environment snapshot.

## Render + Neon migration notes

### Current sideline processing mode (development): **bypass**

For development right now, keep the worker service scaled to `0` (or disabled). In this mode:

- `POST /sidelines` requests are accepted and persisted.
- Jobs are enqueued to Redis Streams.
- Status remains `queued` because no worker is consuming.

### How to enable sideline processing later

1. Scale `chessground-worker` to at least one instance.
2. Set `STOCKFISH_PATH` to a valid executable path available in the worker runtime (for example `/usr/games/stockfish`, if installed there).
3. Verify worker startup:

   ```bash
   uv run --no-sync python -m backend.worker_service
   ```

4. Trigger a sideline request and poll `GET /sidelines/{request_id}` to confirm status transitions from `queued` to `completed` or `failed`.

If a request stays `queued`, check worker scale, Redis/Postgres connectivity, and the configured `STOCKFISH_PATH`.

You can run a full web deployment on Render by splitting into services:

- Web service: Next.js app from `web/` (`npm run build && npm run start`)
- API service: `uv run --no-sync uvicorn backend.api_service:app --host 0.0.0.0 --port $PORT`
- Worker service: `uv run --no-sync python -m backend.worker_service`
- Redis: Render Key Value/Redis instance
- Postgres: Neon database

For Neon-only data reads in API `GET /games*`, set:

- Web: `API_BASE_URL=<https://your-api-service.onrender.com>`. This is a server-only value used by the same-origin `/api/backend` proxy. Do not publish `API_AUTH_TOKEN` through a `NEXT_PUBLIC_*` value; users sign in with their API token at `/login`.
- API: `DATA_BACKEND=postgres`, `ENFORCE_POSTGRES_ON_RENDER=1`, `POSTGRES_DSN=<neon connection string>`, `REDIS_URL=<render redis url>`, `API_AUTH_TOKEN=<shared token>`, `API_CORS_ORIGINS=<https://your-web-service.onrender.com>`
- Worker: `POSTGRES_DSN=<neon connection string>`, `REDIS_URL=<render redis url>`, `STOCKFISH_PATH=<engine path>`

After changing env vars, redeploy web/API/worker.

Then run:

```bash
uv run --no-sync python -m backend.bootstrap_postgres_schema
```

The API reads games/moves/positions from Postgres.

Use `DATA_BACKEND=postgres` for local development to match production.
