-- PostgreSQL normalized opening graph schema
-- Edge-level dedupe is global; lines are compositions of edge references.

CREATE TABLE IF NOT EXISTS positions (
    pos_id BIGSERIAL PRIMARY KEY,
    fen_norm TEXT NOT NULL UNIQUE,
    zobrist BIGINT NOT NULL,
    material_key TEXT,
    side_to_move CHAR(1) NOT NULL CHECK (side_to_move IN ('w', 'b')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS edges (
    edge_id BIGSERIAL PRIMARY KEY,
    pos_id BIGINT NOT NULL REFERENCES positions(pos_id) ON DELETE CASCADE,
    uci_move TEXT NOT NULL,
    next_pos_id BIGINT NOT NULL REFERENCES positions(pos_id) ON DELETE CASCADE,
    global_weight INTEGER NOT NULL DEFAULT 0,
    quality_state TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (pos_id, uci_move, next_pos_id)
);

CREATE INDEX IF NOT EXISTS idx_edges_pos_id ON edges(pos_id);
CREATE INDEX IF NOT EXISTS idx_edges_next_pos_id ON edges(next_pos_id);

-- Optional UI/history grouping by sequence of deduplicated edges.
CREATE TABLE IF NOT EXISTS lines (
    line_id BIGSERIAL PRIMARY KEY,
    line_name TEXT,
    source_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS line_membership (
    line_id BIGINT NOT NULL REFERENCES lines(line_id) ON DELETE CASCADE,
    seq_no INTEGER NOT NULL,
    edge_id BIGINT NOT NULL REFERENCES edges(edge_id) ON DELETE RESTRICT,
    PRIMARY KEY (line_id, seq_no),
    UNIQUE (line_id, edge_id, seq_no)
);

CREATE INDEX IF NOT EXISTS idx_line_membership_edge_id ON line_membership(edge_id);

-- One chosen mainline edge per (position, user).
CREATE TABLE IF NOT EXISTS user_mainline (
    pos_id BIGINT NOT NULL REFERENCES positions(pos_id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    edge_id BIGINT NOT NULL REFERENCES edges(edge_id) ON DELETE CASCADE,
    chosen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pos_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_mainline_user_id ON user_mainline(user_id);
CREATE INDEX IF NOT EXISTS idx_user_mainline_edge_id ON user_mainline(edge_id);

-- Optional denormalized cache for rapid path expansion from a root position.
-- Store as edge_id and/or pos_id arrays so cache invalidation can stay cheap.
CREATE TABLE IF NOT EXISTS line_path_cache (
    root_pos_id BIGINT NOT NULL REFERENCES positions(pos_id) ON DELETE CASCADE,
    line_id BIGINT REFERENCES lines(line_id) ON DELETE CASCADE,
    edge_path BIGINT[] NOT NULL,
    pos_path BIGINT[] NOT NULL,
    depth INTEGER GENERATED ALWAYS AS (COALESCE(array_length(edge_path, 1), 0)) STORED,
    cache_version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (root_pos_id, line_id)
);

CREATE INDEX IF NOT EXISTS idx_line_path_cache_line_id ON line_path_cache(line_id);
CREATE INDEX IF NOT EXISTS idx_line_path_cache_root_pos ON line_path_cache(root_pos_id);

CREATE OR REPLACE FUNCTION touch_edges_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edges_touch_updated_at ON edges;
CREATE TRIGGER trg_edges_touch_updated_at
BEFORE UPDATE ON edges
FOR EACH ROW
EXECUTE FUNCTION touch_edges_updated_at();

-- Invalidate cached path rows when an edge affecting a root/line path changes.
CREATE OR REPLACE FUNCTION invalidate_line_path_cache_for_edge()
RETURNS TRIGGER AS $$
DECLARE
    affected_edge_id BIGINT;
    affected_pos_id BIGINT;
    affected_next_pos_id BIGINT;
BEGIN
    affected_edge_id := COALESCE(NEW.edge_id, OLD.edge_id);
    affected_pos_id := COALESCE(NEW.pos_id, OLD.pos_id);
    affected_next_pos_id := COALESCE(NEW.next_pos_id, OLD.next_pos_id);

    DELETE FROM line_path_cache lpc
    WHERE affected_edge_id = ANY (lpc.edge_path)
       OR affected_pos_id = lpc.root_pos_id
       OR affected_next_pos_id = lpc.root_pos_id
       OR affected_pos_id = ANY (lpc.pos_path)
       OR affected_next_pos_id = ANY (lpc.pos_path);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_invalidate_line_path_cache_on_edge_ins ON edges;
DROP TRIGGER IF EXISTS trg_invalidate_line_path_cache_on_edge_upd ON edges;
DROP TRIGGER IF EXISTS trg_invalidate_line_path_cache_on_edge_del ON edges;

CREATE TRIGGER trg_invalidate_line_path_cache_on_edge_ins
AFTER INSERT ON edges
FOR EACH ROW
EXECUTE FUNCTION invalidate_line_path_cache_for_edge();

CREATE TRIGGER trg_invalidate_line_path_cache_on_edge_upd
AFTER UPDATE OF pos_id, uci_move, next_pos_id, global_weight, quality_state ON edges
FOR EACH ROW
EXECUTE FUNCTION invalidate_line_path_cache_for_edge();

CREATE TRIGGER trg_invalidate_line_path_cache_on_edge_del
AFTER DELETE ON edges
FOR EACH ROW
EXECUTE FUNCTION invalidate_line_path_cache_for_edge();
