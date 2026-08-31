-- Canonical PostgreSQL runtime schema.
-- Existing single-workspace rows are assigned to the seeded default workspace.

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO workspaces(id, slug, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'default', 'Default workspace')
ON CONFLICT (id) DO NOTHING;

-- The retired normalized-graph experiment also used the name `positions`, but
-- exposed `pos_id` instead of the application model's `id`. Preserve it under
-- an explicitly experimental name rather than trying to make two incompatible
-- schemas share one table.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='positions' AND column_name='pos_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='positions' AND column_name='id'
    ) THEN
        ALTER TABLE positions RENAME TO graph_positions_experimental;
    END IF;
END $$;

CREATE SEQUENCE IF NOT EXISTS positions_id_seq;
CREATE SEQUENCE IF NOT EXISTS games_id_seq;

CREATE TABLE IF NOT EXISTS positions (
    id BIGINT PRIMARY KEY DEFAULT nextval('positions_id_seq'),
    fen_norm TEXT NOT NULL UNIQUE,
    zobrist BIGINT,
    material_key TEXT,
    side_to_move TEXT
);

ALTER TABLE positions ADD COLUMN IF NOT EXISTS zobrist BIGINT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS material_key TEXT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS side_to_move TEXT;

CREATE TABLE IF NOT EXISTS repertoire_lines (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    line_id TEXT NOT NULL,
    canonical_path_hash TEXT NOT NULL,
    source_pgn TEXT,
    is_priority INTEGER NOT NULL DEFAULT 0,
    side_to_play TEXT NOT NULL DEFAULT 'white',
    metadata_json JSONB,
    PRIMARY KEY (workspace_id, line_id),
    UNIQUE (workspace_id, canonical_path_hash)
);

ALTER TABLE repertoire_lines ADD COLUMN IF NOT EXISTS workspace_id UUID;
UPDATE repertoire_lines SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE repertoire_lines ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE repertoire_lines ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS line_id_sequences (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    base_id TEXT NOT NULL,
    next_suffix INTEGER NOT NULL DEFAULT 2,
    PRIMARY KEY (workspace_id, base_id)
);

CREATE TABLE IF NOT EXISTS repertoire_compact (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    line_id TEXT NOT NULL,
    moves_json JSONB NOT NULL,
    san_moves_json JSONB NOT NULL,
    pos_ids_json JSONB NOT NULL,
    ply_count INTEGER NOT NULL,
    PRIMARY KEY (workspace_id, line_id),
    FOREIGN KEY (workspace_id, line_id)
        REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE
);

ALTER TABLE repertoire_compact ADD COLUMN IF NOT EXISTS workspace_id UUID;
UPDATE repertoire_compact SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE repertoire_compact ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE repertoire_compact ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS repertoire_edges (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    pos_id BIGINT NOT NULL REFERENCES positions(id),
    uci_move TEXT NOT NULL,
    san_move TEXT,
    next_pos_id BIGINT NOT NULL REFERENCES positions(id),
    weight INTEGER NOT NULL DEFAULT 0,
    is_priority_edge INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, pos_id, uci_move, next_pos_id)
);

CREATE TABLE IF NOT EXISTS user_mainline_overrides (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    pos_id BIGINT NOT NULL REFERENCES positions(id),
    uci_move TEXT NOT NULL,
    next_pos_id BIGINT NOT NULL REFERENCES positions(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, pos_id)
);

CREATE TABLE IF NOT EXISTS source_artifacts (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('repertoire', 'game')),
    provider TEXT NOT NULL DEFAULT 'upload',
    original_name TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    pgn_text TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, source_type, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_source_artifacts_workspace_type
    ON source_artifacts(workspace_id, source_type, imported_at DESC);
ALTER TABLE source_artifacts DROP CONSTRAINT IF EXISTS source_artifacts_workspace_id_id_key;
ALTER TABLE source_artifacts ADD CONSTRAINT source_artifacts_workspace_id_key
    UNIQUE (workspace_id, id);

DO $$
BEGIN
    IF to_regclass('public.fetched_game_sources') IS NOT NULL THEN
        INSERT INTO source_artifacts(
            id, workspace_id, source_type, provider, original_name,
            content_hash, pgn_text, metadata_json, imported_at, updated_at
        )
        SELECT gen_random_uuid(), '00000000-0000-0000-0000-000000000001'::uuid,
               'game', provider, format('%s-%s.pgn', provider, username),
               pgn_hash, pgn_text, jsonb_build_object('username', username),
               fetched_at, fetched_at
        FROM fetched_game_sources
        ON CONFLICT (workspace_id, source_type, content_hash) DO NOTHING;
    END IF;
END $$;

DROP TABLE IF EXISTS fetched_game_sources;

CREATE TABLE IF NOT EXISTS games (
    id BIGINT PRIMARY KEY DEFAULT nextval('games_id_seq'),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_artifact_id UUID REFERENCES source_artifacts(id) ON DELETE SET NULL,
    pgn_hash TEXT NOT NULL,
    source_pgn TEXT,
    event TEXT,
    site TEXT,
    date TEXT,
    utc_date TEXT,
    utc_time TEXT,
    white TEXT,
    black TEXT,
    result TEXT,
    time_control TEXT,
    white_elo INTEGER,
    black_elo INTEGER,
    player_color TEXT,
    is_daily INTEGER NOT NULL DEFAULT 0,
    termination TEXT,
    eco TEXT,
    UNIQUE (workspace_id, pgn_hash)
);

ALTER TABLE games ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE games ADD COLUMN IF NOT EXISTS source_artifact_id UUID;
UPDATE games SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE games ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE games ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS game_positions (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    pos_id BIGINT NOT NULL REFERENCES positions(id),
    san_move TEXT,
    uci_move TEXT,
    clock_seconds DOUBLE PRECISION,
    time_spent_seconds DOUBLE PRECISION,
    time_spent_fraction DOUBLE PRECISION,
    is_self INTEGER NOT NULL,
    repertoire_class TEXT,
    PRIMARY KEY (workspace_id, game_id, ply)
);

ALTER TABLE game_positions ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE game_positions ADD COLUMN IF NOT EXISTS next_pos_id BIGINT REFERENCES positions(id);
UPDATE game_positions SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE game_positions ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE game_positions ALTER COLUMN workspace_id SET NOT NULL;
UPDATE game_positions AS current_position
SET next_pos_id = following_position.pos_id
FROM game_positions AS following_position
WHERE current_position.workspace_id = following_position.workspace_id
  AND current_position.game_id = following_position.game_id
  AND following_position.ply = current_position.ply + 1
  AND current_position.next_pos_id IS NULL;

CREATE TABLE IF NOT EXISTS matches (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    analysis_run_id UUID NOT NULL,
    matched_line_id TEXT,
    matching_mode TEXT,
    max_matched_ply INTEGER,
    deviation_ply_you INTEGER,
    deviation_ply_opp INTEGER,
    compliance TEXT,
    who_left_first TEXT,
    recovered_to_rep INTEGER NOT NULL DEFAULT 0,
    opponent_dev_to_known INTEGER NOT NULL DEFAULT 0,
    tags_json JSONB,
    tie_lines_json JSONB,
    PRIMARY KEY (workspace_id, analysis_run_id, game_id)
);

ALTER TABLE matches ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS analysis_run_id UUID;
UPDATE matches SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE matches ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE matches ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS engine_cache (
    pos_id BIGINT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    depth INTEGER NOT NULL,
    engine_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'fixed',
    max_time_ms INTEGER NOT NULL DEFAULT 0,
    options_hash TEXT NOT NULL DEFAULT '',
    best_uci TEXT,
    eval_cp INTEGER,
    wdl_json JSONB,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pos_id, depth, engine_id, mode, max_time_ms, options_hash)
);

ALTER TABLE engine_cache ALTER COLUMN max_time_ms SET DEFAULT 0;
UPDATE engine_cache SET max_time_ms=0 WHERE max_time_ms IS NULL;
ALTER TABLE engine_cache ALTER COLUMN max_time_ms SET NOT NULL;
ALTER TABLE engine_cache DROP CONSTRAINT IF EXISTS engine_cache_pkey;
ALTER TABLE engine_cache ADD CONSTRAINT engine_cache_pkey
    PRIMARY KEY (pos_id, depth, engine_id, mode, max_time_ms, options_hash);

CREATE TABLE IF NOT EXISTS analysis_ply (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    analysis_run_id UUID NOT NULL,
    ply INTEGER NOT NULL,
    pos_id BIGINT NOT NULL REFERENCES positions(id),
    pre_eval_cp INTEGER,
    post_eval_cp INTEGER,
    best_uci TEXT,
    your_cpl INTEGER,
    rep_cpl INTEGER,
    quality_label TEXT,
    repertoire_class TEXT,
    PRIMARY KEY (workspace_id, analysis_run_id, game_id, ply)
);

ALTER TABLE analysis_ply ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE analysis_ply ADD COLUMN IF NOT EXISTS analysis_run_id UUID;
ALTER TABLE analysis_ply ADD COLUMN IF NOT EXISTS repertoire_class TEXT;
UPDATE analysis_ply SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE analysis_ply ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE analysis_ply ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS time_patterns (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    analysis_run_id UUID NOT NULL,
    slow_in_book INTEGER NOT NULL DEFAULT 0,
    instant_out_of_book INTEGER NOT NULL DEFAULT 0,
    blunder_cluster INTEGER NOT NULL DEFAULT 0,
    details_json JSONB,
    PRIMARY KEY (workspace_id, analysis_run_id, game_id)
);

CREATE TABLE IF NOT EXISTS review_items (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    analysis_run_id UUID,
    line_id TEXT,
    reason TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_propositions (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    proposition_type TEXT NOT NULL,
    proposition_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    threshold_count INTEGER NOT NULL DEFAULT 0,
    dismissed_count INTEGER NOT NULL DEFAULT 0,
    pos_id BIGINT REFERENCES positions(id),
    uci_move TEXT,
    line_id_hint TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detail_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    UNIQUE (workspace_id, proposition_key),
    UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS branch_queue (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    proposition_id BIGINT NOT NULL,
    queue_status TEXT NOT NULL DEFAULT 'queued',
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (proposition_id),
    FOREIGN KEY (workspace_id, proposition_id)
        REFERENCES review_propositions(workspace_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS insights (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    analysis_run_id UUID,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT NOT NULL,
    data_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trainer_line_state (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    line_id TEXT NOT NULL,
    side_to_play TEXT NOT NULL DEFAULT 'white',
    learned INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0,
    times_correct INTEGER NOT NULL DEFAULT 0,
    times_incorrect INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    priority_override INTEGER NOT NULL DEFAULT 0,
    auto_priority_score INTEGER NOT NULL DEFAULT 0,
    focus_max_ply INTEGER,
    PRIMARY KEY (workspace_id, line_id),
    FOREIGN KEY (workspace_id, line_id)
        REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE
);

ALTER TABLE trainer_line_state ADD COLUMN IF NOT EXISTS workspace_id UUID;
UPDATE trainer_line_state SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE trainer_line_state ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE trainer_line_state ALTER COLUMN workspace_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS trainer_sessions (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    line_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    player_move_index INTEGER NOT NULL DEFAULT 0,
    had_incorrect INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (workspace_id, line_id)
        REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE
);

ALTER TABLE trainer_sessions ADD COLUMN IF NOT EXISTS workspace_id UUID;
UPDATE trainer_sessions SET workspace_id = '00000000-0000-0000-0000-000000000001' WHERE workspace_id IS NULL;
ALTER TABLE trainer_sessions ALTER COLUMN workspace_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
ALTER TABLE trainer_sessions ALTER COLUMN workspace_id SET NOT NULL;

-- Upgrade uniqueness and foreign keys from the former one-workspace schema.
ALTER TABLE games DROP CONSTRAINT IF EXISTS games_pgn_hash_key;
ALTER TABLE games DROP CONSTRAINT IF EXISTS games_workspace_id_pgn_hash_key;
ALTER TABLE games ADD CONSTRAINT games_workspace_pgn_hash_key UNIQUE (workspace_id, pgn_hash);

ALTER TABLE repertoire_compact DROP CONSTRAINT IF EXISTS repertoire_compact_line_id_fkey;
ALTER TABLE repertoire_compact DROP CONSTRAINT IF EXISTS repertoire_compact_workspace_id_line_id_fkey;
ALTER TABLE trainer_line_state DROP CONSTRAINT IF EXISTS trainer_line_state_line_id_fkey;
ALTER TABLE trainer_line_state DROP CONSTRAINT IF EXISTS trainer_line_state_workspace_id_line_id_fkey;
ALTER TABLE trainer_sessions DROP CONSTRAINT IF EXISTS trainer_sessions_line_id_fkey;
ALTER TABLE trainer_sessions DROP CONSTRAINT IF EXISTS trainer_sessions_workspace_id_line_id_fkey;

ALTER TABLE repertoire_compact DROP CONSTRAINT IF EXISTS repertoire_compact_pkey;
ALTER TABLE trainer_line_state DROP CONSTRAINT IF EXISTS trainer_line_state_pkey;
ALTER TABLE repertoire_lines DROP CONSTRAINT IF EXISTS repertoire_lines_pkey;
ALTER TABLE repertoire_lines DROP CONSTRAINT IF EXISTS repertoire_lines_canonical_path_hash_key;
ALTER TABLE repertoire_lines DROP CONSTRAINT IF EXISTS repertoire_lines_workspace_id_canonical_path_hash_key;
ALTER TABLE game_positions DROP CONSTRAINT IF EXISTS game_positions_pkey;

ALTER TABLE repertoire_lines ADD CONSTRAINT repertoire_lines_pkey PRIMARY KEY (workspace_id, line_id);
ALTER TABLE repertoire_lines ADD CONSTRAINT repertoire_lines_workspace_path_key
    UNIQUE (workspace_id, canonical_path_hash);
ALTER TABLE repertoire_compact ADD CONSTRAINT repertoire_compact_pkey PRIMARY KEY (workspace_id, line_id);
ALTER TABLE repertoire_compact ADD CONSTRAINT repertoire_compact_line_fkey
    FOREIGN KEY (workspace_id, line_id) REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE;
ALTER TABLE trainer_line_state ADD CONSTRAINT trainer_line_state_pkey PRIMARY KEY (workspace_id, line_id);
ALTER TABLE trainer_line_state ADD CONSTRAINT trainer_line_state_line_fkey
    FOREIGN KEY (workspace_id, line_id) REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE;
ALTER TABLE trainer_sessions ADD CONSTRAINT trainer_sessions_line_fkey
    FOREIGN KEY (workspace_id, line_id) REFERENCES repertoire_lines(workspace_id, line_id) ON DELETE CASCADE;
ALTER TABLE game_positions ADD CONSTRAINT game_positions_pkey PRIMARY KEY (workspace_id, game_id, ply);

ALTER TABLE games DROP CONSTRAINT IF EXISTS games_workspace_id_fkey;
ALTER TABLE games DROP CONSTRAINT IF EXISTS games_source_artifact_id_fkey;
ALTER TABLE games DROP CONSTRAINT IF EXISTS games_workspace_id_id_key;
ALTER TABLE games ADD CONSTRAINT games_workspace_fkey
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE games ADD CONSTRAINT games_source_artifact_fkey
    FOREIGN KEY (workspace_id, source_artifact_id)
    REFERENCES source_artifacts(workspace_id, id) ON DELETE RESTRICT;
ALTER TABLE games ADD CONSTRAINT games_workspace_id_key UNIQUE (workspace_id, id);

ALTER TABLE repertoire_lines DROP CONSTRAINT IF EXISTS repertoire_lines_workspace_id_fkey;
ALTER TABLE repertoire_lines ADD CONSTRAINT repertoire_lines_workspace_fkey
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;

ALTER TABLE game_positions DROP CONSTRAINT IF EXISTS game_positions_workspace_id_fkey;
ALTER TABLE game_positions DROP CONSTRAINT IF EXISTS game_positions_game_id_fkey;
ALTER TABLE game_positions ADD CONSTRAINT game_positions_workspace_fkey
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE game_positions ADD CONSTRAINT game_positions_game_fkey
    FOREIGN KEY (workspace_id, game_id) REFERENCES games(workspace_id, id) ON DELETE CASCADE;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_workspace_id_fkey;
ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_game_id_fkey;
ALTER TABLE matches ADD CONSTRAINT matches_workspace_fkey
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE matches ADD CONSTRAINT matches_game_fkey
    FOREIGN KEY (workspace_id, game_id) REFERENCES games(workspace_id, id) ON DELETE CASCADE;

ALTER TABLE analysis_ply DROP CONSTRAINT IF EXISTS analysis_ply_workspace_id_fkey;
ALTER TABLE analysis_ply DROP CONSTRAINT IF EXISTS analysis_ply_game_id_fkey;
ALTER TABLE analysis_ply ADD CONSTRAINT analysis_ply_workspace_fkey
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE analysis_ply ADD CONSTRAINT analysis_ply_game_fkey
    FOREIGN KEY (workspace_id, game_id) REFERENCES games(workspace_id, id) ON DELETE CASCADE;

ALTER TABLE time_patterns DROP CONSTRAINT IF EXISTS time_patterns_game_id_fkey;
ALTER TABLE time_patterns ADD CONSTRAINT time_patterns_game_fkey
    FOREIGN KEY (workspace_id, game_id) REFERENCES games(workspace_id, id) ON DELETE CASCADE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'runtime_settings' AND column_name = 'scope'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'runtime_settings' AND column_name = 'workspace_id'
    ) THEN
        ALTER TABLE runtime_settings RENAME TO runtime_settings_legacy;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS runtime_settings (
    workspace_id UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF to_regclass('public.runtime_settings_legacy') IS NOT NULL THEN
        INSERT INTO runtime_settings(workspace_id, payload, updated_at)
        SELECT '00000000-0000-0000-0000-000000000001'::uuid, payload, updated_at
        FROM runtime_settings_legacy
        ORDER BY updated_at DESC
        LIMIT 1
        ON CONFLICT (workspace_id) DO NOTHING;
    END IF;
END $$;

DROP TABLE IF EXISTS runtime_settings_legacy;

CREATE TABLE IF NOT EXISTS workspace_state (
    workspace_id UUID PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    active_analysis_run_id UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO workspace_state(workspace_id)
VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (workspace_id) DO NOTHING;

DROP VIEW IF EXISTS line_positions;
CREATE VIEW line_positions AS
SELECT
    rc.workspace_id,
    rc.line_id,
    je.idx::INTEGER AS ply,
    (rc.pos_ids_json ->> ((je.idx - 1)::INTEGER))::BIGINT AS pos_id,
    (rc.san_moves_json ->> ((je.idx - 1)::INTEGER)) AS san_move,
    je.value AS uci_move,
    (rc.pos_ids_json ->> (je.idx::INTEGER))::BIGINT AS next_pos_id
FROM repertoire_compact rc
JOIN LATERAL jsonb_array_elements_text(rc.moves_json)
    WITH ORDINALITY AS je(value, idx) ON TRUE;

CREATE INDEX IF NOT EXISTS idx_games_workspace_date ON games(workspace_id, date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_game_positions_workspace_pos ON game_positions(workspace_id, pos_id);
CREATE INDEX IF NOT EXISTS idx_matches_workspace_line ON matches(workspace_id, matched_line_id);
CREATE INDEX IF NOT EXISTS idx_analysis_ply_workspace_game ON analysis_ply(workspace_id, game_id);
CREATE INDEX IF NOT EXISTS idx_repertoire_edges_workspace_pos ON repertoire_edges(workspace_id, pos_id);
CREATE INDEX IF NOT EXISTS idx_review_propositions_workspace_status ON review_propositions(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_trainer_state_workspace_review ON trainer_line_state(workspace_id, needs_review);

SELECT setval('positions_id_seq', COALESCE((SELECT MAX(id) FROM positions), 0) + 1, false);
SELECT setval('games_id_seq', COALESCE((SELECT MAX(id) FROM games), 0) + 1, false);
