from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import sqlite3

SIDELINE_PENDING_STATUSES = ("PENDING", "EVAL_OK", "EVAL_WARN")


def compute_game_hash(tags: dict, moves_uci: list[str]) -> str:
    hasher = hashlib.sha1()
    tag_items = [
        tags.get("Event", ""),
        tags.get("Site", ""),
        tags.get("Date", ""),
        tags.get("White", ""),
        tags.get("Black", ""),
        tags.get("Result", ""),
    ]
    hasher.update("|".join(tag_items).encode("utf-8", errors="ignore"))
    hasher.update("|".join(moves_uci).encode("utf-8", errors="ignore"))
    return hasher.hexdigest()


def fetch_game_overview(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT g.id, g.date, g.white, g.black, g.result, g.time_control,
               g.white_elo, g.black_elo,
               m.matched_line_id AS line_id,
               m.compliance,
               m.max_matched_ply,
               m.matching_mode,
               m.who_left_first,
               (
                   SELECT SUM(CASE WHEN gp.repertoire_class = 'IN_REPERTOIRE_MAIN' THEN 1 ELSE 0 END)
                   FROM game_positions gp
                   WHERE gp.game_id = g.id AND gp.is_self = 1
               ) AS in_main,
               (
                   SELECT SUM(CASE WHEN gp.repertoire_class = 'IN_REPERTOIRE_OTHER' THEN 1 ELSE 0 END)
                   FROM game_positions gp
                   WHERE gp.game_id = g.id AND gp.is_self = 1
               ) AS in_other,
               (
                   SELECT SUM(CASE WHEN gp.repertoire_class = 'OUT_OF_REPERTOIRE' THEN 1 ELSE 0 END)
                   FROM game_positions gp
                   WHERE gp.game_id = g.id AND gp.is_self = 1
               ) AS out_rep
        FROM games g
        LEFT JOIN matches m ON g.id = m.game_id
        ORDER BY g.date DESC, g.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_position_id_by_fen(conn: sqlite3.Connection, fen_norm: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM positions WHERE fen_norm = ?",
        (fen_norm,),
    ).fetchone()
    if not row:
        return None
    return int(row["id"])


def fetch_game_summaries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT g.id, g.date, g.white, g.black, g.result, g.white_elo, g.black_elo,
               g.player_color, g.is_daily, g.time_control,
               m.matched_line_id AS line_id,
               m.max_matched_ply,
               m.deviation_ply_you,
               m.deviation_ply_opp,
               m.compliance,
               m.matching_mode,
               m.opponent_dev_to_known
        FROM games g
        LEFT JOIN matches m ON g.id = m.game_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_game_moves(conn: sqlite3.Connection, game_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT gp.ply, gp.pos_id, gp.san_move, gp.uci_move, gp.repertoire_class, gp.is_self,
               gp.clock_seconds, gp.time_spent_seconds, gp.time_spent_fraction,
               ap.pre_eval_cp, ap.post_eval_cp, ap.best_uci, ap.your_cpl, ap.rep_cpl,
               ap.quality_label
        FROM game_positions gp
        LEFT JOIN analysis_ply ap ON gp.game_id = ap.game_id AND gp.ply = ap.ply
        WHERE gp.game_id = ?
        ORDER BY gp.ply
        """,
        (game_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_game_header(conn: sqlite3.Connection, game_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT g.id, g.date, g.white, g.black, g.result, g.player_color,
               g.white_elo, g.black_elo, g.time_control,
               m.matched_line_id AS line_id,
               m.max_matched_ply,
               m.deviation_ply_you,
               m.deviation_ply_opp,
               m.matching_mode,
               m.compliance,
               m.who_left_first,
               m.tie_lines_json,
               m.tags_json
        FROM games g
        LEFT JOIN matches m ON g.id = m.game_id
        WHERE g.id = ?
        """,
        (game_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    if data.get("tie_lines_json"):
        data["tie_lines"] = json.loads(data["tie_lines_json"])
    else:
        data["tie_lines"] = []
    if data.get("tags_json"):
        data["tags"] = json.loads(data["tags_json"])
    else:
        data["tags"] = []
    return data


def fetch_line_moves(
    conn: sqlite3.Connection, line_id: str, max_ply: int | None = None
) -> list[dict]:
    params = [line_id]
    clause = ""
    if max_ply is not None:
        clause = "AND ply <= ?"
        params.append(max_ply)
    rows = conn.execute(
        f"""
        SELECT ply, san_move, uci_move, pos_id, next_pos_id
        FROM line_positions
        WHERE line_id = ?
        {clause}
        ORDER BY ply
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_line_edge(conn: sqlite3.Connection, line_id: str, ply: int) -> dict | None:
    row = conn.execute(
        """
        SELECT pos_id, uci_move, next_pos_id
        FROM line_positions
        WHERE line_id = ? AND ply = ?
        """,
        (line_id, ply),
    ).fetchone()
    return dict(row) if row else None


def fetch_line_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT line_id FROM repertoire_lines ORDER BY line_id").fetchall()
    return [row["line_id"] for row in rows]


def fetch_eval_at_exit(conn: sqlite3.Connection) -> dict[int, int]:
    rows = conn.execute(
        """
        SELECT ap.game_id, ap.post_eval_cp
        FROM analysis_ply ap
        JOIN matches m ON ap.game_id = m.game_id AND ap.ply = m.max_matched_ply
        """
    ).fetchall()
    return {row["game_id"]: row["post_eval_cp"] for row in rows}


def fetch_time_usage_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT gp.game_id, gp.ply, gp.time_spent_seconds, gp.time_spent_fraction,
               gp.is_self, g.is_daily, gp.repertoire_class, m.max_matched_ply
        FROM game_positions gp
        JOIN games g ON gp.game_id = g.id
        JOIN matches m ON gp.game_id = m.game_id
        WHERE gp.time_spent_seconds IS NOT NULL
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_repertoire_class_counts_by_line(conn: sqlite3.Connection) -> dict[str | None, dict]:
    rows = conn.execute(
        """
        SELECT m.matched_line_id AS line_id,
               SUM(CASE WHEN gp.is_self = 1 AND gp.repertoire_class = 'IN_REPERTOIRE_OTHER' THEN 1 ELSE 0 END) AS in_other,
               SUM(CASE WHEN gp.is_self = 1 AND gp.repertoire_class IN ('IN_REPERTOIRE_MAIN', 'IN_REPERTOIRE_OTHER') THEN 1 ELSE 0 END) AS in_total,
               SUM(CASE WHEN gp.is_self = 1 AND gp.repertoire_class = 'OUT_OF_REPERTOIRE' THEN 1 ELSE 0 END) AS out_total
        FROM game_positions gp
        JOIN matches m ON gp.game_id = m.game_id
        WHERE m.matched_line_id IS NOT NULL
        GROUP BY m.matched_line_id
        """
    ).fetchall()
    return {row["line_id"]: dict(row) for row in rows}


def set_user_mainline(conn: sqlite3.Connection, pos_id: int, uci_move: str, next_pos_id: int) -> None:
    conn.execute("DELETE FROM user_mainline_overrides WHERE pos_id = ?", (pos_id,))
    conn.execute(
        """
        INSERT INTO user_mainline_overrides (pos_id, uci_move, next_pos_id)
        VALUES (?, ?, ?)
        """,
        (pos_id, uci_move, next_pos_id),
    )
    conn.execute(
        """
        UPDATE repertoire_edges
        SET is_user_mainline = CASE
            WHEN pos_id = ? AND uci_move = ? AND next_pos_id = ? THEN 1
            ELSE 0
        END
        WHERE pos_id = ?
        """,
        (pos_id, uci_move, next_pos_id, pos_id),
    )
    conn.commit()


def fetch_review_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT line_id, reason, detail
        FROM review_items
        ORDER BY reason, line_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_review_propositions(
    conn: sqlite3.Connection,
    status_filter: str = "pending",
) -> list[dict]:
    status_key = (status_filter or "pending").strip().lower()
    where = ["proposition_type = ?"]
    params: list = ["MISSING_COVERAGE_BRANCH"]
    if status_key == "pending":
        where.append("status = 'PENDING'")
        where.append("evidence_count > threshold_count")
    elif status_key == "approved":
        where.append("status = 'APPROVED'")
    elif status_key == "disapproved":
        where.append("status = 'DISAPPROVED'")
    elif status_key == "all":
        pass
    else:
        where.append("status = 'PENDING'")
        where.append("evidence_count > threshold_count")

    rows = conn.execute(
        f"""
        SELECT id,
               proposition_type,
               status,
               evidence_count,
               threshold_count,
               pos_id,
               uci_move,
               line_id_hint,
               updated_at
        FROM review_propositions
        WHERE {" AND ".join(where)}
        ORDER BY evidence_count DESC, updated_at DESC, id DESC
        """
        ,
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_review_proposition_detail(
    conn: sqlite3.Connection,
    proposition_id: int,
) -> dict | None:
    row = conn.execute(
        """
        SELECT id,
               proposition_type,
               proposition_key,
               status,
               evidence_count,
               threshold_count,
               dismissed_count,
               pos_id,
               uci_move,
               line_id_hint,
               detail_json,
               created_at,
               updated_at,
               decided_at
        FROM review_propositions
        WHERE id = ?
        """,
        (int(proposition_id),),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    payload = data.get("detail_json")
    if payload:
        try:
            data["detail"] = json.loads(payload)
        except json.JSONDecodeError:
            data["detail"] = None
    else:
        data["detail"] = None
    return data


def approve_review_proposition(
    conn: sqlite3.Connection,
    proposition_id: int,
) -> tuple[bool, str]:
    now_iso = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        """
        UPDATE review_propositions
        SET status = 'APPROVED',
            decided_at = ?,
            updated_at = ?
        WHERE id = ?
          AND proposition_type = 'MISSING_COVERAGE_BRANCH'
        """,
        (now_iso, now_iso, int(proposition_id)),
    )
    if result.rowcount <= 0:
        conn.rollback()
        return False, "Proposition not found."
    conn.execute(
        """
        INSERT OR REPLACE INTO branch_queue (proposition_id, queue_status, queued_at)
        VALUES (?, 'QUEUED', ?)
        """,
        (int(proposition_id), now_iso),
    )
    conn.commit()
    return True, "Proposition approved and queued."


def disapprove_review_proposition(
    conn: sqlite3.Connection,
    proposition_id: int,
) -> tuple[bool, str]:
    row = conn.execute(
        """
        SELECT evidence_count
        FROM review_propositions
        WHERE id = ?
          AND proposition_type = 'MISSING_COVERAGE_BRANCH'
        """,
        (int(proposition_id),),
    ).fetchone()
    if not row:
        return False, "Proposition not found."

    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE review_propositions
        SET status = 'DISAPPROVED',
            dismissed_count = ?,
            decided_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (int(row["evidence_count"] or 0), now_iso, now_iso, int(proposition_id)),
    )
    conn.execute(
        "DELETE FROM branch_queue WHERE proposition_id = ?",
        (int(proposition_id),),
    )
    conn.commit()
    return True, "Proposition disapproved."



def sideline_queue_key(pos_id: int, move_uci: str, target_context: str) -> str:
    payload = f"{int(pos_id)}|{move_uci.strip()}|{target_context.strip()}"
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


def upsert_sideline_queue_request(
    conn: sqlite3.Connection,
    pos_id: int,
    move_uci: str,
    target_context: str,
    requested_by_user_id: str | None = None,
) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    queue_key = sideline_queue_key(pos_id, move_uci, target_context)
    conn.execute(
        """
        INSERT INTO sideline_queue (
            queue_key,
            pos_id,
            move_uci,
            target_context,
            status,
            requested_by_user_id,
            first_seen_at,
            last_seen_at,
            request_count
        )
        VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, 1)
        ON CONFLICT(queue_key) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            request_count = sideline_queue.request_count + 1,
            requested_by_user_id = COALESCE(sideline_queue.requested_by_user_id, excluded.requested_by_user_id)
        """,
        (
            queue_key,
            int(pos_id),
            move_uci,
            target_context,
            requested_by_user_id,
            now_iso,
            now_iso,
        ),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT queue_key, pos_id, move_uci, target_context, status, requested_by_user_id,
               first_seen_at, last_seen_at, request_count, warning_reason, eval_cp_delta, cpl_estimate
        FROM sideline_queue
        WHERE queue_key = ?
        """,
        (queue_key,),
    ).fetchone()
    return dict(row) if row else {"queue_key": queue_key}


def request_sideline_for_game_deviation(
    conn: sqlite3.Connection,
    game_id: int,
    requested_by_user_id: str | None = None,
) -> tuple[bool, str, dict | None]:
    row = conn.execute(
        """
        SELECT gp.pos_id, gp.uci_move, m.deviation_ply_you, m.matched_line_id
        FROM matches m
        JOIN game_positions gp
          ON gp.game_id = m.game_id
         AND gp.ply = m.deviation_ply_you
        WHERE m.game_id = ?
          AND m.compliance = 'YOU_DEVIATED'
          AND m.deviation_ply_you IS NOT NULL
          AND gp.uci_move IS NOT NULL
        """,
        (int(game_id),),
    ).fetchone()
    if not row:
        return False, "No self-deviation move found for this game.", None

    pos_id = int(row["pos_id"])
    move_uci = str(row["uci_move"])
    deviation_ply = int(row["deviation_ply_you"] or 0)
    line_id = row["matched_line_id"] or "unmatched"
    target_context = f"game:{int(game_id)}|line:{line_id}|ply:{deviation_ply}"
    item = upsert_sideline_queue_request(
        conn,
        pos_id=pos_id,
        move_uci=move_uci,
        target_context=target_context,
        requested_by_user_id=requested_by_user_id,
    )
    return True, "Sideline request queued.", item


def update_sideline_queue_status(
    conn: sqlite3.Connection,
    queue_key: str,
    status: str,
    warning_reason: str | None = None,
    eval_cp_delta: int | None = None,
    cpl_estimate: float | None = None,
    next_pos_id: int | None = None,
) -> tuple[bool, str]:
    status_up = (status or "").strip().upper()
    allowed = {"PENDING", "EVAL_OK", "EVAL_WARN", "APPROVED", "FAILED"}
    if status_up not in allowed:
        return False, f"Unsupported sideline status: {status}"

    now_iso = datetime.now(timezone.utc).isoformat()
    result = conn.execute(
        """
        UPDATE sideline_queue
        SET status = ?,
            warning_reason = ?,
            eval_cp_delta = ?,
            cpl_estimate = ?,
            last_seen_at = ?
        WHERE queue_key = ?
        """,
        (status_up, warning_reason, eval_cp_delta, cpl_estimate, now_iso, queue_key),
    )
    if result.rowcount <= 0:
        conn.rollback()
        return False, "Sideline queue item not found."

    if status_up == "APPROVED" and next_pos_id is not None:
        row = conn.execute(
            "SELECT pos_id, move_uci FROM sideline_queue WHERE queue_key = ?",
            (queue_key,),
        ).fetchone()
        if not row:
            conn.rollback()
            return False, "Sideline queue item not found."
        pos_id = int(row["pos_id"])
        move_uci = str(row["move_uci"])

        conn.execute(
            """
            INSERT OR IGNORE INTO repertoire_edges (
                pos_id, uci_move, next_pos_id, weight, sources_json, is_priority_edge, is_user_mainline
            )
            VALUES (?, ?, ?, 1, ?, 0, 0)
            """,
            (
                pos_id,
                move_uci,
                int(next_pos_id),
                json.dumps(["sideline_queue", queue_key]),
            ),
        )

        line_id = f"sideline::{queue_key[:12]}"
        conn.execute(
            """
            INSERT OR IGNORE INTO repertoire_lines (line_id, source_pgn, is_priority, side_to_play, metadata_json)
            VALUES (?, 'sideline_queue', 0, 'white', ?)
            """,
            (line_id, json.dumps({"queue_key": queue_key})),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO repertoire_compact (
                line_id, moves_json, san_moves_json, pos_ids_json, ply_count
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                line_id,
                json.dumps([move_uci]),
                json.dumps([move_uci]),
                json.dumps([pos_id, int(next_pos_id)]),
            ),
        )

    conn.commit()
    return True, "Sideline queue item updated."

def fetch_insights(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT category, title, details, data_json
        FROM insights
        ORDER BY category, title
        """
    ).fetchall()
    results = []
    for row in rows:
        data = dict(row)
        if data.get("data_json"):
            try:
                data["data"] = json.loads(data["data_json"])
            except json.JSONDecodeError:
                data["data"] = None
        else:
            data["data"] = None
        results.append(data)
    return results


def fetch_games_list(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, date, white, black, result
        FROM games
        ORDER BY date DESC, id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_tree_repertoire_children(
    conn: sqlite3.Connection,
    pos_id: int,
    my_side_only: bool = True,
) -> list[dict]:
    having_clause = "HAVING self_count > 0" if my_side_only else ""
    rows = conn.execute(
        f"""
        WITH repertoire_rows AS (
            SELECT lp.uci_move,
                   MIN(lp.san_move) AS san_move,
                   lp.next_pos_id,
                   COUNT(*) AS weight,
                   MAX(CASE WHEN rl.is_priority = 1 THEN 1 ELSE 0 END) AS is_priority_edge,
                   MAX(CASE WHEN re.is_user_mainline = 1 THEN 1 ELSE 0 END) AS is_user_mainline,
                   SUM(
                       CASE
                           WHEN (
                               (rl.side_to_play = 'white' AND (lp.ply % 2) = 1)
                               OR
                               (rl.side_to_play = 'black' AND (lp.ply % 2) = 0)
                           )
                           THEN 1
                           ELSE 0
                       END
                   ) AS self_count,
                   0 AS is_sideline_pending
            FROM line_positions lp
            JOIN repertoire_lines rl
              ON rl.line_id = lp.line_id
            LEFT JOIN repertoire_edges re
              ON re.pos_id = lp.pos_id
             AND re.uci_move = lp.uci_move
             AND re.next_pos_id = lp.next_pos_id
            WHERE lp.pos_id = ?
            GROUP BY lp.uci_move, lp.next_pos_id
            {having_clause}
        ),
        pending_sidelines AS (
            SELECT sq.move_uci AS uci_move,
                   sq.move_uci AS san_move,
                   NULL AS next_pos_id,
                   0 AS weight,
                   0 AS is_priority_edge,
                   0 AS is_user_mainline,
                   CASE WHEN ? = 1 THEN 1 ELSE 0 END AS self_count,
                   1 AS is_sideline_pending
            FROM sideline_queue sq
            WHERE sq.pos_id = ?
              AND sq.status IN ('PENDING', 'EVAL_OK', 'EVAL_WARN')
              AND NOT EXISTS (
                  SELECT 1
                  FROM repertoire_rows rr
                  WHERE rr.uci_move = sq.move_uci
              )
        )
        SELECT *
        FROM repertoire_rows
        UNION ALL
        SELECT *
        FROM pending_sidelines
        ORDER BY is_sideline_pending DESC, weight DESC, uci_move
        """,
        (int(pos_id), 1 if my_side_only else 0, int(pos_id)),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_tree_game_children(
    conn: sqlite3.Connection,
    pos_id: int,
    *,
    my_side_only: bool = True,
    date_from: str | None = None,
    date_to: str | None = None,
    time_class: str = "all",
    opp_elo_min: int | None = None,
    opp_elo_max: int | None = None,
) -> list[dict]:
    filters = ["gp.pos_id = ?"]
    params: list = [int(pos_id)]

    if my_side_only:
        filters.append("gp.is_self = 1")

    if date_from:
        filters.append("g.date >= ?")
        params.append(date_from)
    if date_to:
        filters.append("g.date <= ?")
        params.append(date_to)

    base_seconds_expr = (
        "CASE "
        "WHEN instr(g.time_control, '+') > 0 "
        "THEN CAST(substr(g.time_control, 1, instr(g.time_control, '+') - 1) AS INTEGER) "
        "ELSE NULL END"
    )
    tc = (time_class or "all").strip().lower()
    if tc == "daily":
        filters.append("g.is_daily = 1")
    elif tc == "bullet":
        filters.append("g.is_daily = 0")
        filters.append(f"({base_seconds_expr}) IS NOT NULL")
        filters.append(f"({base_seconds_expr}) <= 180")
    elif tc == "blitz":
        filters.append("g.is_daily = 0")
        filters.append(f"({base_seconds_expr}) > 180")
        filters.append(f"({base_seconds_expr}) <= 600")
    elif tc == "rapid":
        filters.append("g.is_daily = 0")
        filters.append(f"({base_seconds_expr}) > 600")
        filters.append(f"({base_seconds_expr}) <= 3600")
    elif tc == "other":
        filters.append(
            "g.is_daily = 0 AND "
            f"(({base_seconds_expr}) IS NULL OR ({base_seconds_expr}) > 3600)"
        )

    opp_elo_expr = (
        "CASE "
        "WHEN g.player_color = 'white' THEN g.black_elo "
        "ELSE g.white_elo END"
    )
    if opp_elo_min is not None and int(opp_elo_min) > 0:
        filters.append(f"({opp_elo_expr}) >= ?")
        params.append(int(opp_elo_min))
    if opp_elo_max is not None and int(opp_elo_max) > 0:
        filters.append(f"({opp_elo_expr}) <= ?")
        params.append(int(opp_elo_max))

    where_clause = " AND ".join(filters) if filters else "1=1"
    rows = conn.execute(
        f"""
        SELECT gp.uci_move,
               MIN(gp.san_move) AS san_move,
               MIN(gp_next.pos_id) AS next_pos_id,
               COUNT(*) AS games,
               SUM(
                   CASE
                       WHEN (
                           (g.result = '1-0' AND g.player_color = 'white')
                           OR
                           (g.result = '0-1' AND g.player_color = 'black')
                       ) THEN 1 ELSE 0
                   END
               ) AS wins,
               SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END) AS draws,
               SUM(
                   CASE
                       WHEN (
                           (g.result = '0-1' AND g.player_color = 'white')
                           OR
                           (g.result = '1-0' AND g.player_color = 'black')
                       ) THEN 1 ELSE 0
                   END
               ) AS losses,
               AVG({opp_elo_expr}) AS avg_opp_elo
        FROM game_positions gp
        JOIN games g
          ON g.id = gp.game_id
        LEFT JOIN game_positions gp_next
          ON gp_next.game_id = gp.game_id
         AND gp_next.ply = gp.ply + 1
        WHERE {where_clause}
        GROUP BY gp.uci_move
        ORDER BY games DESC, gp.uci_move
        """,
        tuple(params),
    ).fetchall()

    out: list[dict] = []
    for row in rows:
        entry = dict(row)
        total = int(entry.get("games") or 0)
        wins = int(entry.get("wins") or 0)
        draws = int(entry.get("draws") or 0)
        entry["score_pct"] = ((wins + 0.5 * draws) / total * 100.0) if total > 0 else 0.0
        out.append(entry)
    return out


def fetch_tree_position_games(
    conn: sqlite3.Connection,
    pos_id: int,
    uci_move: str,
    limit: int = 20,
) -> list[dict]:
    opp_elo_expr = (
        "CASE "
        "WHEN g.player_color = 'white' THEN g.black_elo "
        "ELSE g.white_elo END"
    )
    rows = conn.execute(
        f"""
        SELECT g.id AS game_id,
               g.date,
               g.white,
               g.black,
               g.result,
               g.player_color,
               {opp_elo_expr} AS opp_elo,
               gp.ply
        FROM game_positions gp
        JOIN games g
          ON g.id = gp.game_id
        WHERE gp.pos_id = ?
          AND gp.uci_move = ?
        ORDER BY g.date DESC, g.id DESC
        LIMIT ?
        """,
        (int(pos_id), uci_move, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def ensure_trainer_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO trainer_line_state (line_id, side_to_play)
        SELECT line_id, COALESCE(side_to_play, 'white')
        FROM repertoire_lines
        """
    )
    conn.execute(
        """
        UPDATE trainer_line_state
        SET side_to_play = (
            SELECT COALESCE(rl.side_to_play, 'white')
            FROM repertoire_lines rl
            WHERE rl.line_id = trainer_line_state.line_id
        )
        WHERE line_id IN (SELECT line_id FROM repertoire_lines)
        """
    )
    conn.commit()


def fetch_trainer_line_info(conn: sqlite3.Connection, line_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT rl.line_id, rl.side_to_play, rl.is_priority,
               tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
               tls.auto_priority_score, tls.focus_max_ply
        FROM repertoire_lines rl
        JOIN trainer_line_state tls ON rl.line_id = tls.line_id
        WHERE rl.line_id = ?
        """,
        (line_id,),
    ).fetchone()
    return dict(row) if row else None


def fetch_trainer_candidates(conn: sqlite3.Connection, learned_only: bool) -> list[dict]:
    rows = conn.execute(
        """
        SELECT rl.line_id, rl.is_priority, rl.side_to_play,
               tls.learned, tls.needs_review, tls.correct_streak, tls.priority_override,
               tls.auto_priority_score, tls.focus_max_ply
        FROM repertoire_lines rl
        JOIN trainer_line_state tls ON rl.line_id = tls.line_id
        WHERE tls.learned = ?
        """,
        (1 if learned_only else 0,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_trainer_state(
    conn: sqlite3.Connection,
    line_id: str,
    learned: int | None = None,
    needs_review: int | None = None,
    correct_streak: int | None = None,
    times_correct_delta: int = 0,
    times_incorrect_delta: int = 0,
    last_seen: str | None = None,
) -> None:
    fields = []
    params: list = []
    if learned is not None:
        fields.append("learned = ?")
        params.append(int(learned))
    if needs_review is not None:
        fields.append("needs_review = ?")
        params.append(int(needs_review))
    if correct_streak is not None:
        fields.append("correct_streak = ?")
        params.append(int(correct_streak))
    if times_correct_delta:
        fields.append("times_correct = times_correct + ?")
        params.append(int(times_correct_delta))
    if times_incorrect_delta:
        fields.append("times_incorrect = times_incorrect + ?")
        params.append(int(times_incorrect_delta))
    if last_seen is not None:
        fields.append("last_seen = ?")
        params.append(last_seen)

    if not fields:
        return

    params.append(line_id)
    conn.execute(
        f"""
        UPDATE trainer_line_state
        SET {", ".join(fields)}
        WHERE line_id = ?
        """,
        params,
    )
    conn.commit()


def toggle_trainer_priority(conn: sqlite3.Connection, line_id: str) -> int:
    row = conn.execute(
        "SELECT priority_override FROM trainer_line_state WHERE line_id = ?",
        (line_id,),
    ).fetchone()
    current = int(row["priority_override"]) if row else 0
    new_value = 0 if current == 1 else 1
    conn.execute(
        """
        UPDATE trainer_line_state
        SET priority_override = ?
        WHERE line_id = ?
        """,
        (new_value, line_id),
    )
    conn.commit()
    return new_value


def set_trainer_priority_override(conn: sqlite3.Connection, line_id: str, value: int) -> None:
    conn.execute(
        """
        UPDATE trainer_line_state
        SET priority_override = ?
        WHERE line_id = ?
        """,
        (int(value), line_id),
    )
    conn.commit()
