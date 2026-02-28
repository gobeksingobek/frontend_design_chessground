# Backend services

This directory introduces two deployable backend processes that keep Neon/Postgres as source of truth while using Redis Streams for transient queueing.

## Services

- `backend.api_service:app` (FastAPI)
  - Validates sideline creation payloads.
  - Requires bearer token auth (`API_AUTH_TOKEN`).
  - Enforces idempotency (`Idempotency-Key`) via a unique Postgres constraint.
  - Writes request records to Postgres, then enqueues jobs to Redis Streams.
  - Exposes read APIs for request status.
  - `GET /games` and `GET /games/{game_id}` for web Phase 2 games/game-detail screens (reads from SQLite analysis DB).

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

```bash
uvicorn backend.api_service:app --host 0.0.0.0 --port 8000
python -m backend.worker_service
```

## Required env vars

- `POSTGRES_DSN` (Neon/Postgres DSN)
- `REDIS_URL`
- `API_AUTH_TOKEN`
- `SQLITE_PATH` (default `data/analysis.db`)
- `STOCKFISH_PATH`

Optional tuning:

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
