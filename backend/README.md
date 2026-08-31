# ChessGround backend

The backend is PostgreSQL-only and fails startup if an ordered migration in `storage/postgres/migrations/` has not been applied. Apply migrations explicitly with:

```bash
python -m backend.bootstrap_postgres_schema
python -m backend.bootstrap_postgres_schema --validate-only
```

`backend/api_service.py` exposes authenticated reads, synchronous small mutations, source uploads, and durable job entrypoints. Every long-running analysis, ingest/fetch, reanalysis, review regeneration, and sideline workflow creates `analysis_jobs` and `analysis_job_steps` rows, then publishes an identifier-only message to Redis.

Run services independently:

```bash
uvicorn backend.api_service:app --host 0.0.0.0 --port 8000
python -m backend.worker_service --capability orchestration
python -m backend.worker_service --capability ingest
python -m backend.worker_service --capability engine
```

The API and all workers require `POSTGRES_DSN` and `REDIS_URL`. The API also uses `API_AUTH_TOKEN`, `API_CORS_ORIGINS`, and `WORKSPACE_ID`. The engine worker uses `STOCKFISH_PATH` and `STOCKFISH_DEPTH`. Stream/group, retry, lease, heartbeat, and consumer settings are defined in `backend/settings.py`.

Workers claim steps conditionally in PostgreSQL, heartbeat leases, commit results before acknowledging Redis, recover abandoned pending messages with `XAUTOCLAIM`, and send exhausted failures to the workload dead-letter stream. PostgreSQL remains authoritative if a Redis message is delivered more than once.

`GET /operations/metrics` reports durable job failures/stalls/durations, worker heartbeats, retry and engine-slot counts, cache hit rate, and Redis stream lag/pending/dead-letter counts. Deployment alerts should target stalled jobs, missing heartbeats, growing pending/dead-letter counts, and repeated workspace failures.

Source upload formats are `.pgn` and `.zip` containing PGNs. The API stores normalized raw PGN text and content metadata in `source_artifacts` before it queues ingest.
