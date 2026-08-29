-- PostgreSQL schema for analysis/game data currently stored in SQLite.
-- This enables Neon-backed reads for /games and /games/{id} APIs.

CREATE SEQUENCE IF NOT EXISTS positions_id_seq;
CREATE SEQUENCE IF NOT EXISTS games_id_seq;

CREATE TABLE IF NOT EXISTS positions (
    id BIGINT PRIMARY KEY DEFAULT nextval('positions_id_seq'),
    fen_norm TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS games (
    id BIGINT PRIMARY KEY DEFAULT nextval('games_id_seq'),
    pgn_hash TEXT UNIQUE NOT NULL,
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
    eco TEXT
);

ALTER TABLE positions ALTER COLUMN id SET DEFAULT nextval('positions_id_seq');
ALTER TABLE games ALTER COLUMN id SET DEFAULT nextval('games_id_seq');

CREATE TABLE IF NOT EXISTS game_positions (
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
    PRIMARY KEY (game_id, ply)
);

CREATE TABLE IF NOT EXISTS matches (
    game_id BIGINT PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
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
    tie_lines_json JSONB
);

CREATE TABLE IF NOT EXISTS analysis_ply (
    game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    pos_id BIGINT NOT NULL REFERENCES positions(id),
    pre_eval_cp INTEGER,
    post_eval_cp INTEGER,
    best_uci TEXT,
    your_cpl INTEGER,
    rep_cpl INTEGER,
    quality_label TEXT,
    PRIMARY KEY (game_id, ply)
);

CREATE INDEX IF NOT EXISTS idx_game_positions_game_id ON game_positions(game_id);
CREATE INDEX IF NOT EXISTS idx_game_positions_pos_id ON game_positions(pos_id);
CREATE INDEX IF NOT EXISTS idx_matches_line_id ON matches(matched_line_id);
CREATE INDEX IF NOT EXISTS idx_analysis_ply_game_id ON analysis_ply(game_id);

CREATE TABLE IF NOT EXISTS fetched_game_sources (
    pgn_hash TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    username TEXT NOT NULL,
    pgn_text TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fetched_game_sources_fetched_at ON fetched_game_sources(fetched_at DESC);

SELECT setval('positions_id_seq', COALESCE((SELECT MAX(id) FROM positions), 0) + 1, false);
SELECT setval('games_id_seq', COALESCE((SELECT MAX(id) FROM games), 0) + 1, false);


-- Repertoire/trainer tables for trainer session APIs.
CREATE TABLE IF NOT EXISTS repertoire_lines (
    line_id TEXT PRIMARY KEY,
    canonical_path_hash TEXT NOT NULL UNIQUE,
    source_pgn TEXT,
    is_priority INTEGER NOT NULL DEFAULT 0,
    side_to_play TEXT NOT NULL DEFAULT 'white',
    metadata_json JSONB
);

ALTER TABLE repertoire_lines
    ADD COLUMN IF NOT EXISTS is_priority INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS repertoire_compact (
    line_id TEXT PRIMARY KEY REFERENCES repertoire_lines(line_id) ON DELETE CASCADE,
    moves_json JSONB NOT NULL,
    san_moves_json JSONB NOT NULL,
    pos_ids_json JSONB NOT NULL,
    ply_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trainer_line_state (
    line_id TEXT PRIMARY KEY REFERENCES repertoire_lines(line_id) ON DELETE CASCADE,
    side_to_play TEXT NOT NULL DEFAULT 'white',
    learned INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0,
    times_correct INTEGER NOT NULL DEFAULT 0,
    times_incorrect INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    priority_override INTEGER NOT NULL DEFAULT 0,
    auto_priority_score INTEGER NOT NULL DEFAULT 0,
    focus_max_ply INTEGER
);

ALTER TABLE trainer_line_state
    ADD COLUMN IF NOT EXISTS auto_priority_score INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS trainer_sessions (
    id UUID PRIMARY KEY,
    line_id TEXT NOT NULL REFERENCES repertoire_lines(line_id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    player_move_index INTEGER NOT NULL DEFAULT 0,
    had_incorrect INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW line_positions AS
SELECT
    rc.line_id,
    je.idx::INTEGER AS ply,
    (rc.pos_ids_json ->> ((je.idx - 1)::INTEGER))::BIGINT AS pos_id,
    (rc.san_moves_json ->> ((je.idx - 1)::INTEGER)) AS san_move,
    je.value AS uci_move,
    (rc.pos_ids_json ->> (je.idx::INTEGER))::BIGINT AS next_pos_id
FROM repertoire_compact rc
JOIN LATERAL jsonb_array_elements_text(rc.moves_json) WITH ORDINALITY AS je(value, idx) ON TRUE;

CREATE INDEX IF NOT EXISTS idx_trainer_state_needs_review ON trainer_line_state(needs_review);
CREATE INDEX IF NOT EXISTS idx_trainer_sessions_line_id ON trainer_sessions(line_id);
