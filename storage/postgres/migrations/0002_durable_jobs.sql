CREATE TABLE IF NOT EXISTS analysis_jobs (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    parent_job_id UUID,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'retry', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    progress_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB,
    error_code TEXT,
    error_detail TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    cancellation_requested BOOLEAN NOT NULL DEFAULT FALSE,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS analysis_job_steps (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    workload_class TEXT NOT NULL CHECK (workload_class IN ('orchestration', 'engine', 'ingest')),
    step_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'retry', 'completed', 'failed', 'cancelled')),
    durable_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB,
    deduplication_key TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    next_attempt_at TIMESTAMPTZ,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    error_code TEXT,
    error_detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, deduplication_key)
);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_workspace_status
    ON analysis_jobs(workspace_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_job_steps_ready
    ON analysis_job_steps(workload_class, status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_analysis_job_steps_job
    ON analysis_job_steps(job_id, status);

ALTER TABLE analysis_jobs ADD CONSTRAINT analysis_jobs_workspace_id_key
    UNIQUE (workspace_id, id);
ALTER TABLE analysis_jobs ADD CONSTRAINT analysis_jobs_parent_fkey
    FOREIGN KEY (workspace_id, parent_job_id)
    REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
ALTER TABLE analysis_job_steps DROP CONSTRAINT IF EXISTS analysis_job_steps_job_id_fkey;
ALTER TABLE analysis_job_steps ADD CONSTRAINT analysis_job_steps_job_fkey
    FOREIGN KEY (workspace_id, job_id)
    REFERENCES analysis_jobs(workspace_id, id) ON DELETE CASCADE;

-- Preserve already-imported PostgreSQL analysis rows as the first completed
-- result set when upgrading the former single-workspace schema.
INSERT INTO analysis_jobs(
    id, workspace_id, job_type, status, idempotency_key, request_json,
    progress_json, result_json, finished_at
)
SELECT '00000000-0000-0000-0000-000000000002'::uuid,
       '00000000-0000-0000-0000-000000000001'::uuid,
       'legacy-postgres-import', 'completed', 'migration:legacy-postgres-analysis',
       '{}'::jsonb, '{}'::jsonb, '{"migrated": true}'::jsonb, NOW()
WHERE EXISTS (SELECT 1 FROM matches WHERE analysis_run_id IS NULL)
   OR EXISTS (SELECT 1 FROM analysis_ply WHERE analysis_run_id IS NULL)
ON CONFLICT (id) DO NOTHING;

UPDATE matches
SET analysis_run_id='00000000-0000-0000-0000-000000000002'::uuid
WHERE analysis_run_id IS NULL;
UPDATE analysis_ply
SET analysis_run_id='00000000-0000-0000-0000-000000000002'::uuid
WHERE analysis_run_id IS NULL;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_pkey;
ALTER TABLE analysis_ply DROP CONSTRAINT IF EXISTS analysis_ply_pkey;
ALTER TABLE matches ALTER COLUMN analysis_run_id SET NOT NULL;
ALTER TABLE analysis_ply ALTER COLUMN analysis_run_id SET NOT NULL;
ALTER TABLE matches ADD CONSTRAINT matches_pkey PRIMARY KEY (workspace_id, analysis_run_id, game_id);
ALTER TABLE analysis_ply ADD CONSTRAINT analysis_ply_pkey
    PRIMARY KEY (workspace_id, analysis_run_id, game_id, ply);

UPDATE workspace_state
SET active_analysis_run_id='00000000-0000-0000-0000-000000000002'::uuid, updated_at=NOW()
WHERE workspace_id='00000000-0000-0000-0000-000000000001'::uuid
  AND active_analysis_run_id IS NULL
  AND EXISTS (
      SELECT 1 FROM analysis_jobs
      WHERE id='00000000-0000-0000-0000-000000000002'::uuid
  );

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'matches_analysis_run_fk') THEN
        ALTER TABLE matches ADD CONSTRAINT matches_analysis_run_fk
            FOREIGN KEY (workspace_id, analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'analysis_ply_analysis_run_fk') THEN
        ALTER TABLE analysis_ply ADD CONSTRAINT analysis_ply_analysis_run_fk
            FOREIGN KEY (workspace_id, analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'time_patterns_analysis_run_fk') THEN
        ALTER TABLE time_patterns ADD CONSTRAINT time_patterns_analysis_run_fk
            FOREIGN KEY (workspace_id, analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'review_items_analysis_run_fk') THEN
        ALTER TABLE review_items ADD CONSTRAINT review_items_analysis_run_fk
            FOREIGN KEY (workspace_id, analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'insights_analysis_run_fk') THEN
        ALTER TABLE insights ADD CONSTRAINT insights_analysis_run_fk
            FOREIGN KEY (workspace_id, analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'workspace_state_active_run_fk') THEN
        ALTER TABLE workspace_state ADD CONSTRAINT workspace_state_active_run_fk
            FOREIGN KEY (workspace_id, active_analysis_run_id)
            REFERENCES analysis_jobs(workspace_id, id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'sideline_requests' AND column_name = 'status'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'sideline_requests' AND column_name = 'job_id'
    ) THEN
        ALTER TABLE sideline_requests RENAME TO sideline_requests_legacy;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS sideline_requests (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_id UUID NOT NULL UNIQUE,
    game_id TEXT NOT NULL,
    move_ply INTEGER NOT NULL,
    requested_by TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (workspace_id, job_id)
        REFERENCES analysis_jobs(workspace_id, id) ON DELETE CASCADE
);

DO $$
DECLARE
    legacy RECORD;
    migrated_job_id UUID;
BEGIN
    IF to_regclass('public.sideline_requests_legacy') IS NOT NULL THEN
        FOR legacy IN SELECT * FROM sideline_requests_legacy LOOP
            migrated_job_id := legacy.id;
            INSERT INTO analysis_jobs(
                id, workspace_id, job_type, status, idempotency_key, request_json,
                result_json, error_detail, attempts, created_at, updated_at
            ) VALUES (
                migrated_job_id,
                '00000000-0000-0000-0000-000000000001'::uuid,
                'sideline-analysis',
                CASE legacy.status
                    WHEN 'queued' THEN 'queued'
                    WHEN 'pending' THEN 'queued'
                    WHEN 'processing' THEN 'queued'
                    WHEN 'running' THEN 'queued'
                    WHEN 'completed' THEN 'completed'
                    WHEN 'done' THEN 'completed'
                    WHEN 'failed' THEN 'failed'
                    WHEN 'error' THEN 'failed'
                    WHEN 'cancelled' THEN 'cancelled'
                    ELSE 'failed'
                END,
                legacy.idempotency_key,
                legacy.payload,
                legacy.result,
                legacy.error,
                legacy.attempts,
                legacy.created_at,
                legacy.updated_at
            ) ON CONFLICT (id) DO NOTHING;
            IF legacy.status IN ('queued', 'pending', 'processing', 'running') THEN
                INSERT INTO analysis_job_steps(
                    id, job_id, workspace_id, workload_class, step_type, status,
                    durable_payload, deduplication_key, attempts, max_attempts,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    migrated_job_id,
                    '00000000-0000-0000-0000-000000000001'::uuid,
                    'engine',
                    'sideline-analysis',
                    'queued',
                    legacy.payload,
                    'legacy:sideline-analysis',
                    legacy.attempts,
                    GREATEST(legacy.attempts + 1, 3),
                    legacy.created_at,
                    legacy.updated_at
                ) ON CONFLICT (job_id, deduplication_key) DO NOTHING;
            END IF;
            INSERT INTO sideline_requests(
                id, workspace_id, job_id, game_id, move_ply, requested_by, payload, created_at, updated_at
            ) VALUES (
                legacy.id,
                '00000000-0000-0000-0000-000000000001'::uuid,
                migrated_job_id,
                legacy.game_id,
                legacy.move_ply,
                legacy.requested_by,
                legacy.payload,
                legacy.created_at,
                legacy.updated_at
            ) ON CONFLICT (id) DO NOTHING;
        END LOOP;
    END IF;
END $$;

DROP TABLE IF EXISTS sideline_requests_legacy;
