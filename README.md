# ChessGround

ChessGround is a chess repertoire analysis application with a FastAPI backend, capability-specific Redis Streams workers, PostgreSQL storage, a PySide desktop client, and a Next.js web client.

## Runtime architecture

- PostgreSQL is the only persistent runtime database and the authority for application data, source PGNs, settings, jobs, progress, retries, errors, and results.
- Redis Streams deliver durable PostgreSQL job-step pointers to orchestration, engine, and ingest workers. Messages are replay-safe delivery signals, not the job record.
- Desktop and web clients use the backend API. They never connect to PostgreSQL or run canonical analysis locally.
- Server Stockfish workers produce every persisted engine result. Browser WASM evaluation is advisory only.
- Uploaded and fetched source PGNs are stored as `source_artifacts`; analysis does not depend on server-local input paths.

The streams are `chessground:jobs:orchestration`, `chessground:jobs:engine`, and `chessground:jobs:ingest`. Each capability has a separate consumer group and `:dead` dead-letter stream.

## Local services

Set at least:

```text
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/chessground
REDIS_URL=redis://localhost:6379/0
API_AUTH_TOKEN=dev-token
API_CORS_ORIGINS=http://localhost:3000
```

Apply migrations before starting any service:

```bash
python -m backend.bootstrap_postgres_schema
```

Start the API and one worker per capability:

```bash
uvicorn backend.api_service:app --host 0.0.0.0 --port 8000
python -m backend.worker_service --capability orchestration
python -m backend.worker_service --capability ingest
python -m backend.worker_service --capability engine
```

The engine worker also requires `STOCKFISH_PATH`, and production services require a versioned `STOCKFISH_ENGINE_ID`. `STOCKFISH_DEPTH`, lease, retry, stream, group, and worker consumer-name settings are deployment environment variables in `backend/settings.py`.

## Clients and imports

The desktop client reads `config/settings.ini`. This file contains only backend URL/token and optional local upload convenience directories and piece assets. Workspace analysis and fetch settings are stored through `/settings/runtime` in PostgreSQL.

Run the desktop client with `python main.py`. Run the web client with `npm --prefix web run dev`.

`POST /repertoires/import` and `POST /games/import` accept one `.pgn` file or a `.zip` containing PGNs. Job-creating requests require `Idempotency-Key` and return HTTP 202 with a durable job ID. Poll `/jobs/{job_id}` and `/jobs/{job_id}/steps`.

## Validation

```bash
python -m pytest -q
npm --prefix web run test:ui-regression
npm --prefix web run check:settings-contract
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

Real PostgreSQL/Redis integration tests require `RUN_INTEGRATION_TESTS=1`, `POSTGRES_DSN`, and `REDIS_URL`. CI provisions both services and runs the migration and job-delivery integration suite.

See `AGENTS.md` for repository conventions and `web/README.md` for frontend-specific conventions.
