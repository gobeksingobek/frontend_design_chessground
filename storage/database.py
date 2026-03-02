from __future__ import annotations

import os
import sqlite3
from pathlib import Path

EXPECTED_SCHEMA_VERSION = 6

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
DELETE FROM schema_version;
INSERT INTO schema_version (version) VALUES ({version});

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    fen_norm TEXT UNIQUE NOT NULL,
    zobrist INTEGER,
    material_key TEXT,
    side_to_move TEXT
);

CREATE TABLE IF NOT EXISTS repertoire_lines (
    line_id TEXT PRIMARY KEY,
    source_pgn TEXT,
    is_priority INTEGER NOT NULL DEFAULT 0,
    side_to_play TEXT NOT NULL DEFAULT 'white',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS repertoire_compact (
    line_id TEXT PRIMARY KEY,
    moves_json TEXT NOT NULL,
    san_moves_json TEXT NOT NULL,
    pos_ids_json TEXT NOT NULL,
    ply_count INTEGER NOT NULL,
    FOREIGN KEY(line_id) REFERENCES repertoire_lines(line_id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS line_positions AS
SELECT
    rc.line_id AS line_id,
    CAST(je.key AS INTEGER) + 1 AS ply,
    CAST(json_extract(rc.pos_ids_json, '$[' || CAST(je.key AS INTEGER) || ']') AS INTEGER) AS pos_id,
    json_extract(rc.san_moves_json, '$[' || CAST(je.key AS INTEGER) || ']') AS san_move,
    je.value AS uci_move,
    CAST(json_extract(rc.pos_ids_json, '$[' || (CAST(je.key AS INTEGER) + 1) || ']') AS INTEGER) AS next_pos_id
FROM repertoire_compact rc
JOIN json_each(rc.moves_json) je;

CREATE TABLE IF NOT EXISTS repertoire_edges (
    pos_id INTEGER NOT NULL,
    uci_move TEXT NOT NULL,
    next_pos_id INTEGER NOT NULL,
    weight INTEGER NOT NULL,
    sources_json TEXT,
    is_priority_edge INTEGER NOT NULL DEFAULT 0,
    is_user_mainline INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pos_id, uci_move, next_pos_id),
    FOREIGN KEY(pos_id) REFERENCES positions(id),
    FOREIGN KEY(next_pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS user_mainline_overrides (
    pos_id INTEGER NOT NULL,
    uci_move TEXT NOT NULL,
    next_pos_id INTEGER NOT NULL,
    PRIMARY KEY (pos_id, uci_move, next_pos_id),
    FOREIGN KEY(pos_id) REFERENCES positions(id),
    FOREIGN KEY(next_pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS trainer_line_state (
    line_id TEXT PRIMARY KEY,
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
    FOREIGN KEY(line_id) REFERENCES repertoire_lines(line_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_files (
    path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_type TEXT NOT NULL,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
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
    game_id INTEGER NOT NULL,
    ply INTEGER NOT NULL,
    pos_id INTEGER NOT NULL,
    san_move TEXT,
    uci_move TEXT,
    clock_seconds REAL,
    time_spent_seconds REAL,
    time_spent_fraction REAL,
    is_self INTEGER NOT NULL,
    repertoire_class TEXT,
    PRIMARY KEY (game_id, ply),
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS matches (
    game_id INTEGER PRIMARY KEY,
    matched_line_id TEXT,
    matching_mode TEXT,
    max_matched_ply INTEGER,
    deviation_ply_you INTEGER,
    deviation_ply_opp INTEGER,
    compliance TEXT,
    who_left_first TEXT,
    recovered_to_rep INTEGER NOT NULL DEFAULT 0,
    opponent_dev_to_known INTEGER NOT NULL DEFAULT 0,
    tags_json TEXT,
    tie_lines_json TEXT,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS engine_cache (
    pos_id INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    engine_id TEXT NOT NULL,
    best_uci TEXT,
    eval_cp INTEGER,
    wdl_json TEXT,
    analyzed_at TEXT,
    PRIMARY KEY (pos_id, depth, engine_id),
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS analysis_ply (
    game_id INTEGER NOT NULL,
    ply INTEGER NOT NULL,
    pos_id INTEGER NOT NULL,
    pre_eval_cp INTEGER,
    post_eval_cp INTEGER,
    best_uci TEXT,
    your_cpl INTEGER,
    rep_cpl INTEGER,
    quality_label TEXT,
    PRIMARY KEY (game_id, ply),
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS time_patterns (
    game_id INTEGER PRIMARY KEY,
    slow_in_book INTEGER NOT NULL DEFAULT 0,
    instant_out_of_book INTEGER NOT NULL DEFAULT 0,
    blunder_cluster INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY,
    line_id TEXT,
    reason TEXT,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS review_propositions (
    id INTEGER PRIMARY KEY,
    proposition_type TEXT NOT NULL,
    proposition_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'PENDING',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    threshold_count INTEGER NOT NULL DEFAULT 5,
    dismissed_count INTEGER,
    pos_id INTEGER NOT NULL,
    uci_move TEXT NOT NULL,
    line_id_hint TEXT,
    detail_json TEXT,
    created_at TEXT,
    updated_at TEXT,
    decided_at TEXT,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS branch_queue (
    proposition_id INTEGER PRIMARY KEY,
    queue_status TEXT NOT NULL DEFAULT 'QUEUED',
    queued_at TEXT,
    FOREIGN KEY(proposition_id) REFERENCES review_propositions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sideline_queue (
    queue_key TEXT PRIMARY KEY,
    pos_id INTEGER NOT NULL,
    move_uci TEXT NOT NULL,
    target_context TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK(status IN ('PENDING', 'EVAL_OK', 'EVAL_WARN', 'APPROVED', 'FAILED')),
    requested_by_user_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    warning_reason TEXT,
    eval_cp_delta INTEGER,
    cpl_estimate REAL,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY,
    category TEXT,
    title TEXT,
    details TEXT,
    data_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_repertoire_lines_source_pgn ON repertoire_lines(source_pgn);
CREATE INDEX IF NOT EXISTS idx_repertoire_edges_pos_id ON repertoire_edges(pos_id);
CREATE INDEX IF NOT EXISTS idx_game_positions_game_id ON game_positions(game_id);
CREATE INDEX IF NOT EXISTS idx_game_positions_pos_id ON game_positions(pos_id);
CREATE INDEX IF NOT EXISTS idx_matches_line_id ON matches(matched_line_id);
CREATE INDEX IF NOT EXISTS idx_engine_cache_pos_id ON engine_cache(pos_id);
CREATE INDEX IF NOT EXISTS idx_analysis_ply_game_id ON analysis_ply(game_id);
CREATE INDEX IF NOT EXISTS idx_trainer_state_needs_review ON trainer_line_state(needs_review);
CREATE INDEX IF NOT EXISTS idx_review_prop_type_status ON review_propositions(proposition_type, status);
CREATE INDEX IF NOT EXISTS idx_review_prop_status_count ON review_propositions(status, evidence_count);
CREATE INDEX IF NOT EXISTS idx_review_prop_pos_move ON review_propositions(pos_id, uci_move);
CREATE INDEX IF NOT EXISTS idx_sideline_queue_pos_status ON sideline_queue(pos_id, status);
CREATE INDEX IF NOT EXISTS idx_sideline_queue_status ON sideline_queue(status, last_seen_at);
""".format(version=EXPECTED_SCHEMA_VERSION)


RUNTIME_TABLES_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS review_propositions (
    id INTEGER PRIMARY KEY,
    proposition_type TEXT NOT NULL,
    proposition_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'PENDING',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    threshold_count INTEGER NOT NULL DEFAULT 5,
    dismissed_count INTEGER,
    pos_id INTEGER NOT NULL,
    uci_move TEXT NOT NULL,
    line_id_hint TEXT,
    detail_json TEXT,
    created_at TEXT,
    updated_at TEXT,
    decided_at TEXT,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS branch_queue (
    proposition_id INTEGER PRIMARY KEY,
    queue_status TEXT NOT NULL DEFAULT 'QUEUED',
    queued_at TEXT,
    FOREIGN KEY(proposition_id) REFERENCES review_propositions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sideline_queue (
    queue_key TEXT PRIMARY KEY,
    pos_id INTEGER NOT NULL,
    move_uci TEXT NOT NULL,
    target_context TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK(status IN ('PENDING', 'EVAL_OK', 'EVAL_WARN', 'APPROVED', 'FAILED')),
    requested_by_user_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    warning_reason TEXT,
    eval_cp_delta INTEGER,
    cpl_estimate REAL,
    FOREIGN KEY(pos_id) REFERENCES positions(id)
);

CREATE INDEX IF NOT EXISTS idx_review_prop_type_status ON review_propositions(proposition_type, status);
CREATE INDEX IF NOT EXISTS idx_review_prop_status_count ON review_propositions(status, evidence_count);
CREATE INDEX IF NOT EXISTS idx_review_prop_pos_move ON review_propositions(pos_id, uci_move);
CREATE INDEX IF NOT EXISTS idx_sideline_queue_pos_status ON sideline_queue(pos_id, status);
CREATE INDEX IF NOT EXISTS idx_sideline_queue_status ON sideline_queue(status, last_seen_at);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.executescript(RUNTIME_TABLES_SQL)
    conn.commit()


def ensure_runtime_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(RUNTIME_TABLES_SQL)
    conn.commit()


def ensure_db(db_path: str, reset_on_mismatch: bool = True) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = get_connection(db_path)
        init_db(conn)
        return conn

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.Error:
        row = None

    if row and row["version"] == EXPECTED_SCHEMA_VERSION:
        ensure_runtime_tables(conn)
        return conn

    conn.close()
    if reset_on_mismatch:
        if path.exists():
            os.remove(path)
        conn = get_connection(db_path)
        init_db(conn)
        return conn
    raise RuntimeError("Database schema version mismatch.")
