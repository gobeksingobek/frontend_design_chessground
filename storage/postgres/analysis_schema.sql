-- PostgreSQL schema for analysis/game data currently stored in SQLite.
-- This enables Neon-backed reads for /games and /games/{id} APIs.

CREATE TABLE IF NOT EXISTS positions (
    id BIGINT PRIMARY KEY,
    fen_norm TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS games (
    id BIGINT PRIMARY KEY,
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
